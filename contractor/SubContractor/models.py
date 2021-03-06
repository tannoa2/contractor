from cinp.orm_django import DjangoCInP as CInP

from contractor.Utilities.models import AddressBlock
from contractor.Foreman.lib import processJobs, jobResults, jobError

cinp = CInP( 'SubContractor', '0.1' )


# these are only for subcontractor to talk to, thus some of the job_id short cuts
@cinp.staticModel()  # TODO: move to  Foreman?
class Dispatch():
  def __init__( self ):
    super().__init__()

  @cinp.action( return_type={ 'type': 'Map', 'is_array': True }, paramater_type_list=[ { 'type': 'Model', 'model': 'contractor.Site.models.Site' }, { 'type': 'String', 'is_array': True }, 'Integer' ] )
  @staticmethod
  def getJobs( site, module_list, max_jobs=10 ):
    result = processJobs( site, module_list, max_jobs )
    print( '>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> "{0}"'.format( result ))
    return result

  @cinp.action( return_type='String', paramater_type_list=[ 'Integer', 'String', 'Map' ] )
  @staticmethod
  def jobResults( job_id, cookie, data ):
    print( '<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< "{0}" "{1}" "{2}"'.format( job_id, cookie, data ) )
    return jobResults( job_id, cookie, data )

  @cinp.action( paramater_type_list=[ 'Integer', 'String', 'String' ] )
  @staticmethod
  def jobError( job_id, cookie, msg ):
    print( '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! "{0}" "{1}" "{2}"'.format( job_id, cookie, msg ) )
    jobError( job_id, cookie, msg )

  @cinp.check_auth()
  @staticmethod
  def checkAuth( user, method, id_list, action=None ):
    return True


@cinp.staticModel()
class DHCPd():
  def __init__( self ):
    super().__init__()

  @cinp.action( return_type={ 'type': 'Map', 'is_array': True }, paramater_type_list=[ { 'type': 'Model', 'model': 'contractor.Site.models.Site' } ] )
  @staticmethod
  def getDynamicPools( site ):
    result = []
    addr_block_list = AddressBlock.objects.filter( site=site, baseaddress__dynamicaddress__isnull=False )
    for addr_block in addr_block_list:
      item = { 'address_list': {}, 'gateway': addr_block.gateway_ip }
      for addr in addr_block.baseaddress_set.filter( dynamicaddress__isnull=False ):
        addr = addr.subclass
        try:  # TODO: this needs to be retought a bit, really should be passing in the bootfile
          addr.pxe.name
          item[ 'address_list' ][ addr.ip_address ] = 'undionly_console.kpxe'
        except AttributeError:
          item[ 'address_list' ][ addr.ip_address ] = None

    return result

  @cinp.action( return_type={ 'type': 'Map' }, paramater_type_list=[ { 'type': 'Model', 'model': 'contractor.Site.models.Site' } ] )
  @staticmethod
  def getStaticPools( site ):
    result = {}
    addr_block_list = AddressBlock.objects.filter( site=site, baseaddress__address__networked__isnull=False )
    for addr_block in addr_block_list:
      for addr in addr_block.baseaddress_set.filter( address__networked__isnull=False ):
        addr = addr.subclass
        iface = addr.interface
        if iface is None or iface.mac is None:
          continue

        result[ iface.mac ] = {
                                'ip_address': addr.ip_address,
                                'netmask': addr_block.netmask,
                                'gateway': addr_block.gateway_ip,
                                'dns_server': addr_block.dns_servers[0],
                                'host_name': addr.structure.hostname,
                                'domain_name': 'get.from.site.config',
                                'boot_file': 'undionly_console.kpxe'
                              }

    return result

  @cinp.check_auth()
  @staticmethod
  def checkAuth( user, method, id_list, action=None ):
    return True
