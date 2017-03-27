from django.db import models
from django.core.exceptions import ValidationError

from cinp.orm_django import DjangoCInP as CInP

from contractor.fields import MapField, IpAddressField, hostname_regex
from contractor.BluePrint.models import PXE
from contractor.Site.models import Site
from contractor.lib.ip import IpIsV4, CIDRNetworkBounds, StrToIp, IpToStr, CIDRNetworkSize


cinp = CInP( 'Utilities', '0.1' )


@cinp.model( )
class Networked( models.Model ):
  hostname = models.CharField( max_length=100 )
  site = models.ForeignKey( Site, on_delete=models.PROTECT )           # ie where to build it

  class Meta:
    unique_together = ( ( 'site', 'hostname' ), )

  def clean( self, *args, **kwargs ):  # verify hostname
    super().clean( *args, **kwargs )
    errors = {}
    if not hostname_regex.match( self.hostname ):
      errors[ 'hostname' ] = 'Structure hostname "{0}" is invalid'.format( self.hostname )

    if errors:
      raise ValidationError( errors )

  @cinp.check_auth()
  @staticmethod
  def checkAuth( user, method, id_list, action=None ):
    return True

  def __str__( self ):
    return 'Networked "{0}"'.format( self.physical_name )


@cinp.model( not_allowed_method_list=[ 'LIST', 'GET', 'CREATE', 'UPDATE', 'DELETE', 'CALL' ] )
class NetworkInterface( models.Model ):
  updated = models.DateTimeField( editable=False, auto_now=True )
  created = models.DateTimeField( editable=False, auto_now_add=True )

  @property
  def address_list( self ):
    return []

  @property
  def primary_address( self ):
    return 'address'

  @cinp.check_auth()
  @staticmethod
  def checkAuth( user, method, id_list, action=None ):
    if method == 'DESCRIBE':
      return True

    return False

  def __str__( self ):
    return 'NetworkInterface "{0}"'.format( self.physical_name )


@cinp.model( )
class RealNetworkInterface( NetworkInterface ):
  mac = models.CharField( max_length=18, primary_key=True )
  pxe = models.ForeignKey( PXE, related_name='+' )
  physical_name = models.CharField( max_length=20 )

  @cinp.check_auth()
  @staticmethod
  def checkAuth( user, method, id_list, action=None ):
    return True

  def __str__( self ):
    return 'RealNetworkInterface "{0}" mac "{1}"'.format( self.name, self.mac )


@cinp.model( )
class AbstractNetworkInterface( NetworkInterface ):
  logical_name = models.CharField( max_length=20 )

  @cinp.check_auth()
  @staticmethod
  def checkAuth( user, method, id_list, action=None ):
    return True

  def __str__( self ):
    return 'AbstractNetworkInterface "{0}"'.format( self.name )


@cinp.model( )
class AggragatedNetworkInterface( AbstractNetworkInterface ):
  master_interface = models.ForeignKey( NetworkInterface, related_name='+' )
  slaves = models.ManyToManyField( NetworkInterface, related_name='+' )
  paramaters = MapField()

  @cinp.check_auth()
  @staticmethod
  def checkAuth( user, method, id_list, action=None ):
    return True

  def __str__( self ):
    return 'AggragatedNetworkInterface "{0}"'.format( self.name )


@cinp.model()
class AddressBlock( models.Model ):
  cluster = models.ForeignKey( Site, on_delete=models.CASCADE )
  subnet = IpAddressField()
  prefix = models.IntegerField()
  gateway = IpAddressField( blank=True, null=True )
  _max_address = IpAddressField( editable=False )
  updated = models.DateTimeField( editable=False, auto_now=True )
  created = models.DateTimeField( editable=False, auto_now_add=True )

  @property
  def dns_servers( self ):
    return []
    # get config from cluster and return dns servers, if none return empty []

  @property
  def tftp_servers( self ):
    return []

  @property
  def syslog_servers( self ):
    return []

  @property
  def size( self ):
    return CIDRNetworkSize( self.subnet, self.prefix, False )

  def clean( self, *args, **kwargs ):
    super().clean( *args, **kwargs )
    errors = {}
    try:
      subnet_ip = StrToIp( self.subnet )
      ipv4 = IpIsV4( subnet_ip )
    except ValueError:
      ipv4 = None
      errors[ 'subnet' ] = 'Invalid Ip Address'

    if self.prefix < 1:
      errors[ 'prefix' ] = 'Min Prefix is 1'

    if ipv4 is not None:
      if ipv4:
        if self.prefix > 32:
          errors[ 'prefix' ] = 'Max Prefix for ipv4 is 32'
      else:
        if self.prefix > 128:
          errors[ 'prefix' ] = 'Max Prefix for ipv6 is 128'

      try:
        gateway_ip = StrToIp( self.gateway )
        if ipv4 is not IpIsV4( gateway_ip ):
          errors[ 'gateway' ] = 'Not the Same ipv# as Subnet'
      except ValueError:
        errors[ 'gateway' ] = 'Invalid Ip Address'

    if errors:  # no point in continuing until the prefix and subnet are good
      raise ValidationError( errors )

    ( subnet_ip, last_ip ) = CIDRNetworkBounds( subnet_ip, self.prefix, True )
    self.subnet = IpToStr( subnet_ip )
    self._max_address = IpToStr( last_ip )
    block_count = AddressBlock.objects.filter( subnet__gte=self.subnet, _max_address__lte=self.subnet ).count()
    block_count += AddressBlock.objects.filter( subnet__gte=self._max_address, _max_address__lte=self._max_address ).count()
    block_count += AddressBlock.objects.filter( _max_address__gte=self.subnet, _max_address__lte=self._max_address ).count()
    block_count += AddressBlock.objects.filter( subnet__gte=self.subnet, subnet__lte=self._max_address ).count()
    if block_count > 0:
      errors[ 'subnet' ] = 'This subnet/prefix overlaps with an existing Address Block'

    if errors:
      raise ValidationError( errors )

  @cinp.check_auth()
  @staticmethod
  def checkAuth( user, method, id_list, action=None ):
    return True

  def __str__( self ):
    return 'AddressBlock cluster "{0}" subnet "{1}/{2}"'.format( self.cluster, self.subnet, self.prefix )


@cinp.model( not_allowed_method_list=[ 'LIST', 'GET', 'CREATE', 'UPDATE', 'DELETE' ], property_list=( 'address', 'subclass', 'type' ) )
class BaseAddress( models.Model ):
  block = models.ForeignKey( AddressBlock )
  offset = models.IntegerField()
  updated = models.DateTimeField( editable=False, auto_now=True )
  created = models.DateTimeField( editable=False, auto_now_add=True )

  @property
  def address( self ):
    return IpToStr( self.block.subnet + self.offset )

  @property
  def subclass( self ):
    try:
      return self.address
    except AttributeError:
      pass

    try:
      return self.reservedaddress
    except AttributeError:
      pass

    try:
      return self.dynamicaddress
    except AttributeError:
      pass

  @property
  def type( self ):
    'Unknown'

  @cinp.action( return_type={ 'type': 'Model', 'model': 'contractor.Utilitied.models.BaseAddress' }, paramater_type_list=[ 'String' ] )
  @staticmethod
  def lookup( value ):
    value = StrToIp( value )
    try:
      block = AddressBlock.objects.get( subnet__gte=value, _max_address__lte=value )
    except AddressBlock.DoesNotExist:
      return None

    offset = value - block.subnet
    try:
      return BaseAddress.objects.get( block=block, offset=offset )
    except BaseAddress.DoesNotExist:
      return None

  class Meta:
    unique_together = ( ( 'block', 'offset' ), )

  def clean( self, *args, **kwargs ):
    super().clean( *args, **kwargs )
    errors = {}
    block_size = self.block.size
    if block_size == 1:
      if self.offset != 0:
        errors[ 'offset' ] = 'for blocks of size 1, offset must be 0'

    elif block_size == 2:
      if self.offset not in ( 0, 1 ):
        errors[ 'offset' ] = 'for blocks of size 2, offset must be 1 or 2'

    else:
      if self.offset >= self.block.size:
        errors[ 'offset' ] = 'Offset Greater than size of Address Block'
      if self.offset < 1:
        errors[ 'offset' ] = 'Offset must be at least 1'

    if errors:
      raise ValidationError( errors )

  @cinp.check_auth()
  @staticmethod
  def checkAuth( user, method, id_list, action=None ):
    if method == 'DESCRIBE':
      return True

    return False

  def __str__( self ):
    return 'BaseAddress block "{0}" offset "{1}"'.format( self.block, self.offset )


@cinp.model( property_list=( 'state', 'type' ) )
class Address( BaseAddress ):
  networked = models.ForeignKey( Networked )
  is_primary = models.BooleanField( default=False )
  is_provisioning = models.BooleanField( default=False )

  @property
  def subclass( self ):
    return self

  @property
  def type( self ):
    'Address'

  @cinp.check_auth()
  @staticmethod
  def checkAuth( user, method, id_list, action=None ):
    return True

  def __str__( self ):
    return 'Address block "{0}" offset "{1}" networked "{2}"'.format( self.block, self.offset, self.networked )


@cinp.model( property_list=( 'state', 'type' ) )
class ReservedAddress( BaseAddress ):
  reason = models.CharField( max_length=50 )

  @property
  def subclass( self ):
    return self

  @property
  def type( self ):
    'ReservedAddress'

  @cinp.check_auth()
  @staticmethod
  def checkAuth( user, method, id_list, action=None ):
    return True

  def __str__( self ):
    return 'ReservedAddress block "{0}" offset "{1}"'.format( self.block, self.offset )


@cinp.model( property_list=( 'state', 'type' ) )
class DynamicAddress( BaseAddress ):  # no dynamic pools, thoes will be auto detected
  pass

  @property
  def subclass( self ):
    return self

  @property
  def type( self ):
    'DynamicAddress'

  @cinp.check_auth()
  @staticmethod
  def checkAuth( user, method, id_list, action=None ):
    return True

  def __str__( self ):
    return 'DynamicAddress block "{0}" offset "{1}"'.format( self.block, self.offset )


# and Powered
# class PowerPort( models.Model ):
#   other_end = models.ForeignKey( 'self' ) # or should there be a sperate table with the plug relation ships
#   updated = models.DateTimeField( editable=False, auto_now=True )
#   created = models.DateTimeField( editable=False, auto_now_add=True )
#   # powered by Structure
#   # provides power to foundation
