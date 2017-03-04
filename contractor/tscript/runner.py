import uuid
from importlib import import_module

from contractor.tscript.parser import types

from contractor.Building.models import Structure

# thrown when the scipt would like to pause execution, calling run() resumes execution
class Pause( Exception ):
  pass

# resumable error, only differes from pause by the type of exception raised, execution can be resumed with run()
class ExecutionError( Exception ):
  pass

# this error is no-resumable, the script is no longer able to be run()
class UnrecoverableError( Exception ):
  pass

class ScriptError( UnrecoverableError ):
  pass

class ParamaterError( UnrecoverableError ):
  def __init__( self, name, msg, line_no=None ):
    if line_no is not None:
      msg = 'Paramater Error paramater "{0}" line {2}: {1}'.format( name, msg, line_no )
    else:
      msg = 'Paramater Error paramater "{0}": {1}'.format( name, msg )
    super().__init__( msg )
    self.name = name
    self.msg = msg
    self.line_no = line_no

class NotDefinedError( UnrecoverableError ):
  def __init__( self, name, line_no=None ):
    if line_no is not  None:
      msg = 'Not Defined "{0}" line {1}'.format( name, line_no )
    else:
      msg = 'Not Defined "{0}"'.format( name )
    super().__init__( msg )
    self.name = name
    self.line_no = line_no

class Timeout( ExecutionError ):
  def __init__( self, line_no ):
    self.line_no = line_no

class Goto( Exception ):
  def __init__( self, name, line_no ):
    self.name = name
    self.line_no = line_no

class NoRollback( Exception ):
  pass

# for values in modules, the getter/setter must not block, if you need to block
# make a external function

# for an inline non-pausing/remote function, you only need to implement execute and return_value, toSubcontractor is not called if ready is immeditally True.

# any exceptions raised in any of these functions will cause the job the script is running for to end up in error state. Using any Excpetions other than
# ExecutionError and UnrecoverableError will have it's Exception Name displayed in the output, otherwise it is treaded as Unrecoverable... where possible
# use ExecutionError for "normal" errors.  UnrecoverableError will case the Job to enter a perminate Error state where the job can not be resumed.

# Keep in mind that toSubcontractor may be called without the resulting value ever making it to subcontractor.  Network issues, multiple subcontractors
# not all containing all the needed plugins, etc may cause toSubcontractor's output to be discarded.  It may also be possible that subcontractor might
# lock up and never return it's results to fromSubcontractor (lock up, network issues, process terminated, etc.), design acordingly.

# it is perfectly acceptable to not complete the remote function in one request, if some communication betwee contractor and subcontractor modules is needed
# this is allowed, keep in-mind, you may need to handle retries.  When handeling retries, do not rely on counting the number of times toSubcontractor/run/ready
# are called, it is acceptable to store local timers.

# any communication between the contractor and subcontractor pairs must happen between to/fromSubcontractor calls, if an operation requires multiple
# communicatoin routnds, keep in mind that it is possible for multiple subcontractors to be taking requests, so subcontractor must store all state
# with contractor

"""

execution flow:

first execution:
  setup()


reset/rollback event:
  rollback()
  if values to subcontractor is outstanding, that is reset


following executions:
  if ready is False or str:
    run()
    if value dispatched to subcontractor and returned:
      toSubcontractor() -> if not None, value dispatched to subcontractor

  if ready is True:
    value is retreived and returned to script

"""

class ExternalFunction( object ):
  # these two tell contractor what module and function should handle the contractor data
  def __init__( self ):
    super().__init__()

  @property
  def ready( self ):
    # this is called every time contractor wants to know if this script can continue.
    # keep in mind that subcontractor, users, and other processes cause this to be called
    # THIS MUST NOT HANG/PAUSE/WAIT/POLL
    # this is called frequently, keep it light
    # True -> can continue, False -> can not continue, <str> -> is treated as a status message and is displaied (otherwise treated as False)
    # anything else is cast to a string and treaded as a non-resumeable error
    # it is probably wise that this funcion does not do any processing, it may be call multiple times with out any other function in the class being called.
    # do not depend on return_value being called imeditally after ready returns True, ready may have to return True multiple times before the return_value is
    # reterieved and the object is cleaned up.  It is also possible that ready may still be called after return_value is reterieved.
    # NOTE: if ready ever returns True, it can not take that back, bad things may happen.  Including throwing exceptions, they will probably be ignored.
    return True

  @property
  def value( self ):
    # this returns the return value of this function, called only once, after ready returns True
    # THIS MUST NOT HANG/PAUSE/WAIT/POLL
    # if the returned value is an instance of Exception, it is raised and the return value is None, the function is considered executed
    return None

  def run( self ):
    # called after ready is checked and returns False
    # THIS MUST NOT HANG/PAUSE/WAIT/POLL
    pass

  def setup( self, parms ):
    # this function is only called once when the function is first called in the script.
    # parms is a dict of the paramaters passed in from the script
    # if the params are not wnat they should be, raise ParamaterError
    # make sure to do strict saninity checks on the in bound paramaters.
    # THIS MUST NOT HANG/PAUSE/WAIT/POLL
    pass

  def rollback( self ):
    # this is call if there has been an error or loss of communication/tasks with subcontractor
    # and what ever has been done so far needs to be un-done, this mostly applies for VMs
    # and such as a way to clean up any half-baked stuf
    # this must setup the process of rolling back, the regular run, to/fromSubcontractor
    # process is fallowed after rollback is called to complete the job.
    # after rollback is complete, further calls to run, to/from should start rolling forward again
    # if rollback is not possible raise NoRollback
    # THIS MUST NOT HANG/PAUSE/WAIT/POLL
    raise NoRollback()

  def toSubcontractor( self ):
    # this is sent to the subcontractor
    # first paramater is the function inside the plugin to call, second is the value to send to the function
    # this is called initially, then again after fromSubcontractor has returnd results until ready is True
    # example: return ( 'myfunc', { 'stuff': 'for', 'myfunc': 'to use' } ) #NOTE: the paramater part can be anything that is serilizable
    # if None is returned, contractor will not be notified to do anything
    # THIS MUST NOT HANG/PAUSE/WAIT/POLL
    # subcontractor threads will be waiting on this function
    # if there is a problem with the data from subcontractor or some other fatal error occurs,
    #   set ready to True and return an Exception for value, NOTE: this kills this instance of the function unless rolled back
    pass

  def fromSubcontractor( self, data ):
    # return value is send back to contractor so the plugin in contractor can get some feedback
    # data will be a dict
    # this will be called once for every toSubcontractor task sent to subcontractor.  There  could be external
    # logic that looks for timeout/loss of results and call rollback to start from the top
    # THIS MUST NOT HANG/PAUSE/WAIT/POLL
    # subcontractor threads will be waiting on this function, don't do anything to heavy to hold up contractor
    return True

  def __getstate__( self ):
    # return serilizable value that will be passed to __setstate__ when execution is resumed
    return {}

  def __setstate__( self, state ):
    # restore internal state from state
    pass


# used internally to break execution
class Interrupt( Exception ):
  pass


builtin_function_map = {
                          'len':    lambda array: len( array ),
                          'slice':  lambda array, start, end: array[ start:end ],
                          'pop':    lambda array, index: array.pop( index ),
                          'append': lambda array, value: array.append( value ),
                          'index':  lambda array, value: array.index( value ),
                          'pause':  lambda msg: Pause( msg ),
                          'error':  lambda msg: ExecutionError( msg ),
                          'fatal_error': lambda msg: UnrecoverableError( msg )
                        }

infix_math_operator_map = {
                            '+' : lambda a, b: a + b,
                            '-' : lambda a, b: a - b,
                            '*' : lambda a, b: a * b,
                            '/' : lambda a, b: a / b,
                            '%' : lambda a, b: a % b,
                            '^' : lambda a, b: pow( a, b ),
                            '&' : lambda a, b: a & b,
                            '|' : lambda a, b: a | b
                          }

infix_logical_operator_map = {
                               'and': lambda a, b: a and b,
                               'or':  lambda a, b: a or b,
                               '==':  lambda a, b: a == b,
                               '!=':  lambda a, b: a != b,
                               '>=':  lambda a, b: a >= b,
                               '<=':  lambda a, b: a <= b,
                               '>':   lambda a, b: a > b,
                               '<':   lambda a, b: a < b,
                               'not': lambda a, b: not bool( a )
                             }

class Runner( object ):
  def __init__( self, target, ast ):
    super().__init__()
    self.ast = ast
    self.target = target

    # serilize
    self.module_list = []   # list of the loaded plugins
    self.state = []     # list of ( <type>, work values, [ return value ] ), for each level of the AST to the curent execution point
    self.variable_map = {} # map of the variables, they are all global
    self.cur_line = 0
    self.contractor_cookie = None

    # do not serlize
    self.jump_point_map = {}
    self.function_map = {}
    self.value_map = {}

    # setup structure plugin
    if isinstance( target, Structure ):
      self.structure_plugin = StructurePlugin( self.target )
      self.value_map[ 'structure' ] = self.structure_plugin.getValues()
      self.function_map[ 'structure' ] = self.structure_plugin.getFunctions()

    # scan for all the jump points
    for i in range( 0, len( ast[1][ '_children' ] ) ):
      child = ast[1][ '_children' ][i][1] # jump into the  line
      if child[0] == types.JUMP_POINT:
        self.jump_point_map[ child[1] ] = i

  @property
  def line( self ):
    return self.cur_line

  @property
  def done( self ):
    return self.state == 'DONE'

  @property
  def aborted( self ):
    return self.state == 'ABORTED'

  @property
  def status( self ): # list of ( % complete, status message )
    print( ")){0}((".format( self.state ) )
    if self.done or self.aborted:
      return [ ( 100.0, 'Scope', None ) ]
    if len( self.state ) == 0:
      return [ ( 0.0, 'Scope', None ) ]

    item_list = []
    operation = self.ast
    for step in self.state:  #condense into on loop, last status may be a blocking function with remote  and status values
      step_type = step[0]
      try:
        step_data = step[1]
      except IndexError:
        step_data = None

      print( '****** {0}  {1}'.format( operation, step_data ) )

      if step_type == types.SCOPE:
        tmp = operation[1].copy()
        del tmp[ '_children' ]
        if step_data is None: # no point in continuing, we don't know where we are
          item_list.append( ( 0, len( operation[1][ '_children' ] ), 'Scope', tmp ) )
          break
        item_list.append( ( step_data, len( operation[1][ '_children' ] ), 'Scope', tmp ) )
        operation = operation[1][ '_children' ][ step_data ]

      elif step_type == types.WHILE: # if a while loop is on the stack, we must be in it, keep on going
        item_list.append( ( 0, 1, 'While', None ) )
        operation = operation[1][ 'expression' ]

      elif step_type == types.IFELSE:
        pass

      elif step_type == types.LINE:
        operation = operation[1]

      elif step_type == types.FUNCTION:
        tmp = operation[1].copy()
        tmp[ 'dispatched' ] = step_data.get( 'dispatched', None )
        try:
          del tmp[ 'paramaters' ]
        except KeyError:
          pass
        item_list.append( ( 0, 1, 'Function', tmp ) )

      elif step_type in ( types.ASSIGNMENT, types.INFIX, types.CONSTANT, types.VARIABLE, types.GOTO ):
        pass

      else:
        raise Exception( 'Confused step type "{0}"'.format( step_type ) )

    print( item_list )

    result = []
    last_perc_complete = 0
    for item in reversed( item_list ): # work backwards, as we go up, we scale the last perc_complete acording to the % of the curent scope
      # before + -> scaling the last % complete .... after the +  -> the curent %
      perc_complete = ( 1.0 / item[1] ) * last_perc_complete + ( 100.0 * item[0]) / item[1]
      result.insert( 0, ( perc_complete, item[2] , item[3] ) )
      last_perc_complete = perc_complete

    return result

  def goto( self, jump_point ):
    try:
      pos = self.jump_point_map[ jump_point ]
    except KeyError:
      raise NotDefinedError( jump_point )

    self.state = [ [ types.SCOPE, pos ] ]

  def run( self, ttl=1000 ):
    print( '*********************************' )
    if self.aborted:
      return 'aborted'

    if self.done:
      return 'done'

    self.ttl = ttl

    while True: # we are a while loop for the beninit of the goto
      try:
        self._evaluate( self.ast, 0 )
        return ''

      except Goto as e: # yank the stack to this jump point,  NOTE: jump points can only be in the global scope
        try:
          self.goto( e.name )
        except NotDefinedError:
          self.state = 'ABORTED'
          raise NotDefinedError( e.name, e.line_no )

      except Interrupt as e:
        return str( e )

      except ( Pause, ExecutionError ) as e:
        raise e

      except ( UnrecoverableError, ParamaterError, NotDefinedError, ScriptError ) as e:
        self.state = 'ABORTED'
        raise e

      except Exception as e:
        self.state = 'ABORTED'
        raise UnrecoverableError( 'Unahndled Exception ({0}): "{1}"'.format( type( e ).__name__, str( e ) ) )


  def _evaluate( self, operation, state_index ):
    print( '{1}~~~{0}~~~'.format( operation, '.' * state_index ) )
    print( '{1}---{0}---'.format( self.state, '.' * state_index ) )
    op_type = operation[0]
    op_data = operation[1]
    try:
      if self.state[ state_index ][0] != op_type:
        raise Exception( 'State type does not match AST type at {0}. Expected "{1}" got "{2}"'.format( state_index, self.state[ state_index ][0], op_type ) )
    except IndexError:
      self.state.append( [ op_type ] )

    if self.ttl <= 0:
      raise Timeout( self.cur_line )

    self.ttl -= 1

    # NOTE:
    # the logic here can seem a bit funny, however you have to keep
    # in mind that this has to be "re-entrant" ( for lack of a better word )
    # anytime you call _evaluate, execution may be aborted to take care of
    # a blocking function, so you have to check if your state has been setup
    # and sometimes it has to be set up  in stages and checked as if you
    # have or haven't been through it before.
    if op_type == types.LINE:
      self.cur_line = operation[2]
      self._evaluate( op_data, state_index + 1 )

    elif op_type == types.SCOPE:
      try:
        self.state[ state_index ][1]
      except IndexError:
        self.state[ state_index ].append( 0 )

      while self.state[ state_index ][1] < len( op_data[ '_children' ] ):
        self._evaluate( op_data[ '_children' ][ self.state[ state_index ][ 1 ] ], state_index + 1 )
        self.state[ state_index ][1] += 1

    elif op_type == types.CONSTANT: # reterieve constant value
      try:
        self.state[ state_index ][2] = op_data
      except IndexError:
        self.state[ state_index ] += [ None, op_data ]

    elif op_type == types.VARIABLE: # reterieve variable value
      if op_data[ 'module' ] is None:
        try:
          value = self.variable_map[ op_data[ 'name' ] ]
        except KeyError:
          raise NotDefinedError( op_data[ 'name' ], self.cur_line )

      else:
        try:
          module = self.value_map[ op_data[ 'module' ] ]
        except KeyError:
          raise NotDefinedError( op_data[ 'module' ], self.cur_line )

        try:
          value = module[ op_data[ 'name' ] ][0]() # index 0 is the getter
        except KeyError:
          raise NotDefinedError( op_data[ 'name' ], self.cur_line )

      try:
        self.state[ state_index ][2] = value
      except IndexError:
        self.state[ state_index ] += [ None, value ]

    elif op_type == types.ARRAY: # return array
      try:
        self.state[ state_index ][1]
      except IndexError:
        self.state[ state_index ].append( [] )

      for i in range( len( self.state[ state_index ][1] ), len( op_data ) ):
        try:
          self.state[ state_index + 1 ][2]
        except IndexError:
          self._evaluate( op_data[ i ], state_index + 1 )

        self.state[ state_index ][1].append( self.state[ state_index + 1 ][2] )
        self.state = self.state[ :( state_index + 1 ) ]

      self.state[ state_index ].append( self.state[ state_index ][1] )
      self.state[ state_index ][1] = None

    elif op_type == types.ARRAY_ITEM: # reterieve array index value
      try:
        self.state[ state_index ][1]
      except IndexError:
        self.state[ state_index ].append( {} )

      # evaluate the index
      try:
        self.state[ state_index ][1][ 'index' ]
      except KeyError:
        try:
          self.state[ state_index + 1 ][2]
        except IndexError:
          self._evaluate( op_data[ 'index' ], state_index + 1 )

        self.state[ state_index ][1][ 'index' ] = self.state[ state_index + 1 ][2]
        self.state = self.state[ :( state_index + 1 ) ]

      #look up the variable
      if op_data[ 'module' ] is None:
        try:
          value = self.variable_map[ op_data[ 'name' ] ]
        except KeyError:
          raise NotDefinedError( op_data[ 'name' ], self.cur_line )

      else:
        try:
          module = self.value_map[ op_data[ 'module' ] ]
        except KeyError:
          raise NotDefinedError( op_data[ 'module' ], self.cur_line )

        try:
          value = module[ op_data[ 'name' ] ][0]() # index 0 is the getter
        except KeyError:
          raise NotDefinedError( op_data[ 'name' ], self.cur_line )

      value = value[ self.state[ state_index ][1][ 'index' ] ]

      self.state[ state_index ][1] = None
      try:
        self.state[ state_index ][2] = value
      except IndexError:
        self.state[ state_index ].append( value )

    elif op_type == types.ASSIGNMENT: # get the value from 'value', and assign it to the variable defined in 'target'
      if op_data[ 'target' ][0] not in ( types.VARIABLE, types.ARRAY_ITEM ) or ( op_data[ 'target' ][0] == types.ARRAY_ITEM and op_data[ 'target' ][1][ 'module' ] is not None ):
        raise ParamaterError( 'target', 'Can only assign to variables', self.cur_line )

      try:
        self.state[ state_index ][1]
      except IndexError:
        self.state[ state_index ].append( {} )

      if op_data[ 'target' ][0] == types.ARRAY_ITEM:
        try:
          self.state[ state_index ][1][ 'index' ]
        except KeyError:
          try:
            self.state[ state_index + 1 ][2]
          except IndexError:
            self._evaluate( op_data[ 'target' ][1][ 'index' ], state_index + 1 )

          self.state[ state_index ][1][ 'index' ] = self.state[ state_index + 1 ][2]
          self.state = self.state[ :( state_index + 1 ) ]

      try:
        self.state[ state_index ][1][ 'value' ]
      except KeyError:
        try:
          self.state[ state_index + 1 ][2]
        except IndexError:
          self._evaluate( op_data[ 'value' ], state_index + 1 )

        self.state[ state_index ][1][ 'value' ] = self.state[ state_index + 1 ][2]
        self.state = self.state[ :( state_index + 1 ) ]

      target = op_data[ 'target' ][1]
      value = self.state[ state_index ][1][ 'value' ]

      if target[ 'module' ] is None: # we don't evaluate the target, it can only be a variable
        if op_data[ 'target' ][0] == types.ARRAY_ITEM:
          self.variable_map[ target[ 'name' ] ][ self.state[ state_index ][1][ 'index' ] ] = value
        else:
         self.variable_map[ target[ 'name' ] ] = value
      else:
        try:
          module = self.value_map[ target[ 'module' ] ]
        except KeyError:
          raise NotDefinedError( target[ 'module' ], self.cur_line )

        try:
          module[ target[ 'name' ] ][1]( value ) # index 1 is the setter
        except KeyError:
          raise NotDefinedError( target[ 'name' ], self.cur_line )

    elif op_type == types.INFIX: # infix type operators
      try:
        self.state[ state_index ][1]
      except IndexError:
        self.state[ state_index ].append( {} )

      try:
        self.state[ state_index ][1][ 'left' ]
      except KeyError:
        try:
          self.state[ state_index + 1 ][2]
        except IndexError:
          self._evaluate( op_data[ 'left' ], state_index + 1 )

        self.state[ state_index ][1][ 'left' ] = self.state[ state_index + 1 ][2]
        self.state = self.state[ :( state_index + 1 ) ]

      try:
        self.state[ state_index ][1][ 'right' ]
      except KeyError:
        try:
          self.state[ state_index + 1 ][2]
        except IndexError:
          self._evaluate( op_data[ 'right' ], state_index + 1 )

        self.state[ state_index ][1][ 'right' ] = self.state[ state_index + 1 ][2]
        self.state = self.state[ :( state_index + 1 ) ]

      left_val = self.state[ state_index ][1][ 'left' ]
      right_val = self.state[ state_index ][1][ 'right' ]

      if op_data[ 'operator' ] in infix_math_operator_map: # the number group
        if not isinstance( left_val, ( int,  float ) ):
          raise ParamaterError( 'left of operator', 'must be numeric', self.cur_line )
        if not isinstance( right_val, ( int,  float ) ):
          raise ParamaterError( 'right of operator', 'must be numeric', self.cur_line )

        value = infix_math_operator_map[ op_data[ 'operator' ] ]( left_val, right_val )

      elif op_data[ 'operator' ] in infix_logical_operator_map:
        value = infix_logical_operator_map[ op_data[ 'operator' ] ]( left_val, right_val )

      else:
        raise NotDefinedError( op_data[ 'operator' ], self.cur_line )

      self.state[ state_index ][1] = None
      self.state[ state_index ].append( value )

    elif op_type == types.FUNCTION: # FUNCTION
      try:
        self.state[ state_index ][1]
      except IndexError:
        self.state[ state_index ].append( { 'paramaters': {} } )

      if self.state[ state_index ][1] is None: #TODO: is there a better way to handle this?
        pass
        # function allready executed and was an Exceptoin last time, just let things pass by us

      else:
        # get the paramaters
        for key in op_data[ 'paramaters' ]:
          try:
            self.state[ state_index ][1][ 'paramaters' ][ key ]
          except KeyError:
            try:
              self.state[ state_index + 1 ][2]
            except IndexError:
              self._evaluate( op_data[ 'paramaters' ][ key ], state_index + 1 )

            self.state[ state_index ][1][ 'paramaters' ][ key ] = self.state[ state_index + 1 ][2]
            self.state = self.state[ :( state_index + 1 ) ]

        if op_data[ 'module' ] is None:
          # execute builtin function
          try:
            value = builtin_function_map[ op_data[ 'name' ] ]( **self.state[ state_index ][1][ 'paramaters' ] )
          except TypeError as e:
            raise ParamaterError( '<unknown>', e, self.cur_line )
          except KeyError:
            raise NotDefinedError( op_data[ 'name' ], self.cur_line )

        else:
          # execute external function
          try:
            handler = self.state[ state_index ][1][ 'handler' ]
          except KeyError:
            try:
              module = self.function_map[ op_data[ 'module' ] ]
            except KeyError:
              raise NotDefinedError( op_data[ 'module' ], self.cur_line )

            try:
              handler = module[ op_data[ 'name' ] ]()
            except KeyError:
              raise NotDefinedError( op_data[ 'name' ], self.cur_line )

            handler.setup( self.state[ state_index ][1][ 'paramaters' ] )
            self.contractor_cookie = str( uuid.uuid4() )
            self.state[ state_index ][1][ 'handler' ] = handler
            self.state[ state_index ][1][ 'module' ] = op_data[ 'module' ]
            self.state[ state_index ][1][ 'dispatched' ] = False

          ready = handler.ready
          if ready is not True:
            handler.run()
            if ready is False:
              ready = ''
            raise Interrupt( ready )

          value = handler.value

        self.state[ state_index ][1] = None
        if isinstance( value, Exception ):
          self.state[ state_index ].append( None )
          raise value

        else:
          self.state[ state_index ].append( value )

    elif op_type == types.WHILE:
      try:
        self.state[ state_index ][1]
      except IndexError:
        self.state[ state_index ].append( { 'doing': 'condition' } ) # this is so we remember what it was we were doing when interrupted

      while True:
        if self.state[ state_index ][1][ 'doing' ] == 'condition':
          self._evaluate( op_data[ 'condition' ], state_index + 1 )
          if not self.state[ state_index + 1 ][2]:
            break

          self.state[ state_index ][1][ 'doing' ] = 'expression'
          self.state = self.state[ :( state_index + 1 ) ]

        if self.state[ state_index ][1][ 'doing' ] == 'expression':
          self._evaluate( op_data[ 'expression' ], state_index + 1 )
          self.state[ state_index ][1][ 'doing' ] = 'condition'
          self.state = self.state[ :( state_index + 1 ) ]

    elif op_type == types.IFELSE:
      try:
        self.state[ state_index ][1]
      except IndexError:
        self.state[ state_index ].append( { 'index': 0, 'doing': 'condition' } )

      while self.state[ state_index ][1][ 'index' ] < len( op_data ):
        if self.state[ state_index ][1][ 'doing' ] == 'condition':
          if op_data[ self.state[ state_index ][1][ 'index' ] ][ 'condition' ] is None:
            do_expression = True
          else:
            self._evaluate( op_data[ self.state[ state_index ][1][ 'index' ] ][ 'condition' ], state_index + 1 )
            do_expression = self.state[ state_index + 1 ][2]
            self.state = self.state[ :( state_index + 1 ) ]

          if not do_expression:
            self.state[ state_index ][1][ 'index' ] += 1
            continue

          self.state[ state_index ][1][ 'doing' ] = 'expression'

        if self.state[ state_index ][1][ 'doing' ] == 'expression':
          self._evaluate( op_data[ self.state[ state_index ][1][ 'index' ] ][ 'expression' ], state_index + 1 )
          break

        self.state = self.state[ :( state_index + 1 ) ]

    elif op_type == types.JUMP_POINT: # just a NOP execution wise
      pass

    elif op_type == types.GOTO:
      raise Goto( op_data, self.cur_line )

    else:
      raise ScriptError( 'Unimplemented "{0}"'.format( op_type ), self.cur_line )

    # if the op_type we just ran does not  return a value, make sure it is cleaned up
    if op_type not in ( types.CONSTANT, types.VARIABLE, types.ARRAY, types.ARRAY_ITEM, types.INFIX, types.FUNCTION ): # all the things that "return" a value
      self.state = self.state[ :state_index ] # remove this an evertying after from the state
    else:
      self.state = self.state[ :state_index + 1 ] # remove everything after this one, save this one's return value on the stack

    print( '{1}==={0}==='.format( self.state, ' ' * state_index ) )
    if self.state == []:
      self.state = 'DONE'
      self.cur_line = None

  def toSubcontractor( self, module_list ):
    # return None if we done, or not started
    if self.done or self.aborted or self.state == []:
      return None

    operation = self.state[ -1 ]

    # return None if the top of the stack is not a function
    if operation[0] != types.FUNCTION:
      return None

    if operation[1][ 'module' ] not in module_list:
      return None

    if operation[1][ 'dispatched' ] is True: # allready dispatchced, don't send anything else until something comes back
      return None

    handler = operation[1][ 'handler' ]
    ( function_name, paramaters ) = handler.toSubcontractor()
    if paramaters is None:
      return None

    operation[1][ 'dispatched' ] = True

    return { 'module': operation[1][ 'module' ], 'function': function_name, 'cookie': self.contractor_cookie, 'paramaters': paramaters }

  def fromSubcontractor( self, cookie, data ):
    if self.done or self.aborted or self.state == []:
      return 'Script not Running'

    if cookie != self.contractor_cookie:
      return 'Bad Cookie'

    operation = self.state[ -1 ]

    if operation[0] != types.FUNCTION:
      return 'Not At a Function'

    if operation[1][ 'dispatched' ] is False:
      return 'Not Expecting anything'

    handler = operation[1][ 'handler' ]
    handler.fromSubcontractor( data )
    operation[1][ 'dispatched' ] = False

    return 'Accepted'

  def clearDispatched( self ):
    if self.done or self.aborted or self.state == []:
      return

    operation = self.state[ -1 ]

    if operation[0] != types.FUNCTION:
      return

    handler = operation[1][ 'handler' ]
    operation[1][ 'dispatched' ] = False

    return

  def rollback( self ):  #TODO: make to/from subcontractor and  rollback consistant in how they handle errors, this will take some work with the things calling them
    if self.done or self.aborted or self.state == []:
      return 'Script not Running'

    operation = self.state[ -1 ]

    if operation[0] != types.FUNCTION:
      return 'Not At a Function'

    handler = operation[1][ 'handler' ]
    try:
      handler.rollback()
    except NoRollback:
      return 'Rollback not possible'

    self.contractor_cookie = str( uuid.uuid4() ) # revoke any outstanding tasks, TODO: do we also rotate cookie on reset?  if not, should we rotate keys even if rollback is  not possible
    operation[1][ 'dispatched' ] = False

    return 'Done'

  def registerModule( self, name ):
    module = import_module( name )

    if module.TSCRIPT_NAME == 'structure':
      raise Exception( '"structure" module is reserved' )

    self.function_map[ module.TSCRIPT_NAME ] = module.TSCRIPT_FUNCTIONS
    self.value_map[ module.TSCRIPT_NAME ] = module.TSCRIPT_VALUES

    self.module_list.append( name )

  def __reduce__( self ):
    return ( self.__class__, ( self.target, self.ast ), self.__getstate__() )

  def __getstate__( self ):
    return { 'module_list': self.module_list, 'state': self.state, 'variable_map': self.variable_map, 'cur_line': self.cur_line, 'contractor_cookie': self.contractor_cookie }

  def __setstate__( self, state ):
    self.state = state[ 'state' ]
    self.variable_map = state[ 'variable_map' ]
    self.cur_line = state[ 'cur_line' ]
    self.contractor_cookie = state[ 'contractor_cookie' ]
    for module in state[ 'module_list' ]:
      self.registerModule( module )


class StructurePlugin( object ):
  def __init__( self, structure ):
    super().__init__()
    self.structure = structure

  def getValues( self ):
    result = {}
    result[ 'hostname' ] = ( lambda: self.structure.hostname, None )

    return result

  def getFunctions( self ):
    result = {}

    return result
