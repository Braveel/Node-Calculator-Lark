import pymel.core as core
from Lark import (Lark, Transformer)
import itertools


class MayaNode(object):
    def __init__(self, *args):
        self._type = None
        self._attr_type = None
        self._isAttr = False
        self._value = None
        self._init_attr(args)

    def _init_attr(self, args):
        if isinstance(args[0], list):
            args = args[0]

        if len(args) == 1:
            attr_name = args[0]

            if isinstance(attr_name, basestring):
                try:
                    attr = core.PyNode(attr_name)
                except:
                    core.error(' MayaNode: not an attribute')
                if not isinstance(attr, core.general.Attribute):
                    raise Exception("Object must be an attribute, not the node itself")
                if attr.type() in ('doubleLinear', 'doubleAngle', 'float', 'double'):
                    self._type = 'single'
                elif attr.type() in ('float3', 'double3'):
                    self._type = 'vector'
                self._value = attr.name()
                self._attr_type = attr.type()
                self._isAttr = True

            elif isinstance(attr_name, (int, float)):
                self._type = 'single'
                self._attr_type = 'const'
                self._value = attr_name

        elif len(args) < 4:  # length of a vector
            args = list(args)
            values = []

            for i, val in enumerate(args, 1):
                if isinstance(val, basestring):
                    node = MayaNode(val)
                    if node.type == 'vector':
                        raise Exception("Invalid %d-th component vector values" % i)
                    values.append(node)

                elif isinstance(val, MayaNode):
                    if val.type == 'vector':
                        raise Exception("Invalid %d-th component vector values" % i)
                    values.append(val)

                elif isinstance(val, (int, float)):
                    values.append(MayaNode(val))

            if len(values) == 2:
                values.append(MayaNode(0.0))
            self._value = values
            self._type = 'vector'
            self._attr_type = 'compound'

    def __str__(self):
        return '|val: %s, type: %s|' % (self._value, self._type)

    def __repr__(self):
        return '|val: %s, type: %s|' % (self._value, self._type)

    @property
    def isAttr(self):
        return self._isAttr

    @property
    def value(self):
        return self._value

    @property
    def type(self):
        return self._type

    @property
    def typeAttr(self):
        return self._attr_type


def connector(attr, node):
    if node.type == 'single':
        node = itertools.repeat(node, 3)
    else:
        node = node.value

    for k, v in zip(attr.children(), node):
        if v.isAttr:
            core.PyNode(v.value) >> k
        else:
            k.set(v.value)


def expr_func(body):
    v1 = body[0]
    v2 = body[1]

    if v1.type == 'single' and v2.type == 'single':
        if v2.isAttr:
            core.PyNode(v2.value) >> core.PyNode(v1.value)
        if not v2.isAttr:
            print v2
            core.PyNode(v1.value).set(v2.value)

    if v1.type == 'vector' and v2.type == 'vector':
        if v2.isAttr:
            core.PyNode(v2.value) >> core.PyNode(v1.value)
        else:
            connector(core.PyNode(v1.value), v2)

    if v1.type == 'vector' and v2.type == 'single':
        connector(core.PyNode(v1.value), v2)

    if v1.type == 'single' and v2.type == 'vector':
        raise Exception('NOT')

    return v1


def unary_func(body):
    sign = body[0]
    v1 = body[1]

    if sign == -1:
        if v1.type == 'single':
            if not v1.isAttr:
                return MayaNode(-1 * v1.value)
            else:
                MDL = core.createNode('multDoubleLinear')
                MDL.input1.set(-1.)
                core.PyNode(v1.value) >> MDL.input2

                return MayaNode(MDL.output.name())

        if v1.type == 'vector':
            if not v1.isAttr:
                x = -1. * v1.value[0]
                y = -1. * v1.value[1]
                z = -1. * v1.value[2]
                return MayaNode(x, y, z)
            else:
                MD = core.createNode('multiplyDivide')
                MD.input1.set(-1., -1., -1.)
                core.PyNode(v1.value) >> MD.input2

                return MayaNode(MD.output.name())

    else:
        return MayaNode(v1.value)


def sum_sub_func(body, func_operator):
    v1 = body[0]
    v2 = body[1]

    if v1.type == 'single' and v2.type == 'single':
        if not v1.isAttr and not v2.isAttr:
            return MayaNode(func_operator(float(v1.value), float(v2.value)))

        if func_operator.__name__ == '__add__':
            NODE = core.createNode('addDoubleLinear')

            if v1.isAttr and v2.isAttr:
                core.PyNode(v1.value) >> NODE.input1
                core.PyNode(v2.value) >> NODE.input2

            elif v1.isAttr and not v2.isAttr:

                core.PyNode(v1.value) >> NODE.input1
                NODE.input2.set(v2.value)

            elif not v1.isAttr and v2.isAttr:
                NODE.input1.set(v1.value)
                core.PyNode(v2.value) >> NODE.input2

            return MayaNode(NODE.output.name())

        elif func_operator.__name__ == '__sub__':
            NODE = core.createNode('plusMinusAverage')
            NODE.operation.set(2)  # sub

            if v1.isAttr and v2.isAttr:
                core.PyNode(v1.value) >> NODE.input1D[0]
                core.PyNode(v2.value) >> NODE.input1D[1]

            elif v1.isAttr and not v2.isAttr:

                core.PyNode(v1.value) >> NODE.input1D[0]
                NODE.input1D[1].set(v2.value)

            elif not v1.isAttr and v2.isAttr:
                NODE.input1D[0].set(v1.value)
                core.PyNode(v2.value) >> NODE.input1D[1]

            return MayaNode(NODE.output1D.name())

    NODE = core.createNode('plusMinusAverage')
    if func_operator.__name__ == '__add__':
        NODE.operation.set(1)  # add
    elif func_operator.__name__ == '__sub__':
        NODE.operation.set(2)  # sub

    attr1 = NODE.input3D[0]
    attr2 = NODE.input3D[1]

    if v1.type == 'vector' and v2.type == 'vector':
        if not v1.isAttr and not v2.isAttr:
            x = sum_sub_func((v1.value[0], v2.value[0]), func_operator)
            y = sum_sub_func((v1.value[1], v2.value[1]), func_operator)
            z = sum_sub_func((v1.value[2], v2.value[2]), func_operator)

            core.delete(NODE)
            return MayaNode(x, y, z)

        if v1.isAttr and v2.isAttr:
            core.PyNode(v1.value) >> attr1
            core.PyNode(v2.value) >> attr2

        elif v1.isAttr and not v2.isAttr:
            core.PyNode(v1.value) >> attr1
            connector(attr2, v2)

        elif not v1.isAttr and v2.isAttr:
            connector(attr1, v1)
            core.PyNode(v2.value) >> attr2

        return MayaNode(NODE.output3D.name())

    elif v1.type == 'vector' and v2.type == 'single':
        if not v1.isAttr and not v2.isAttr:
            x = sum_sub_func((v1.value[0], v2), func_operator)
            y = sum_sub_func((v1.value[1], v2), func_operator)
            z = sum_sub_func((v1.value[2], v2), func_operator)

            core.delete(NODE)
            return MayaNode(x, y, z)

        if v1.isAttr and v2.isAttr:
            core.PyNode(v1.value) >> attr1
            connector(attr2, v2)

        elif v1.isAttr and not v2.isAttr:
            core.PyNode(v1.value) >> attr1
            connector(attr2, v2)

        elif not v1.isAttr and v2.isAttr:
            connector(attr1, v1)
            connector(attr2, v2)

        return MayaNode(NODE.output3D.name())

    elif v1.type == 'single' and v2.type == 'vector':
        if not v1.isAttr and not v2.isAttr:
            x = sum_sub_func((v2.value[0], v1), func_operator)
            y = sum_sub_func((v2.value[1], v1), func_operator)
            z = sum_sub_func((v2.value[2], v1), func_operator)

            core.delete(NODE)
            return MayaNode(x, y, z)

        if v1.isAttr and v2.isAttr:
            connector(attr1, v1)
            core.PyNode(v2.value) >> attr2

        elif v1.isAttr and not v2.isAttr:
            connector(attr1, v1)
            connector(attr2, v2)

        elif not v1.isAttr and v2.isAttr:
            connector(attr1, v1)
            core.PyNode(v2.value) >> attr2

        return MayaNode(NODE.output3D.name())


def mul_div_pow_func(body, func_operator):
    v1 = body[0]
    v2 = body[1]

    if v1.type == 'single' and v2.type == 'single':
        if not v1.isAttr and not v2.isAttr:
            return MayaNode(func_operator(float(v1.value), float(v2.value)))

        if func_operator.__name__ == '__mul__':
            NODE = core.createNode('multDoubleLinear')

            if v1.isAttr and v2.isAttr:
                core.PyNode(v1.value) >> NODE.input1
                core.PyNode(v2.value) >> NODE.input2

            elif v1.isAttr and not v2.isAttr:

                core.PyNode(v1.value) >> NODE.input1
                NODE.input2.set(v2.value)

            elif not v1.isAttr and v2.isAttr:
                NODE.input1.set(v1.value)
                core.PyNode(v2.value) >> NODE.input2

            return MayaNode(NODE.output.name())

        elif func_operator.__name__ == '__div__' or func_operator.__name__ == '__pow__':
            NODE = core.createNode('multiplyDivide')
            NODE.operation.set(2)  # divide
            if func_operator.__name__ == '__pow__':
                NODE.operation.set(3)  # power

            if v1.isAttr and v2.isAttr:
                core.PyNode(v1.value) >> NODE.input1X
                core.PyNode(v2.value) >> NODE.input2X

            elif v1.isAttr and not v2.isAttr:

                core.PyNode(v1.value) >> NODE.input1X
                NODE.input2X.set(v2.value)

            elif not v1.isAttr and v2.isAttr:
                NODE.input1X.set(v1.value)
                core.PyNode(v2.value) >> NODE.input2X

            return MayaNode(NODE.outputX.name())

    NODE = core.createNode('multiplyDivide')
    if func_operator.__name__ == '__mul__':
        NODE.operation.set(1)  # multiple
    elif func_operator.__name__ == '__div__':
        NODE.operation.set(2)  # divide
    elif func_operator.__name__ == '__pow__':
        NODE.operation.set(3)  # power

    attr1 = NODE.input1
    attr2 = NODE.input2

    if v1.type == 'vector' and v2.type == 'vector':
        if not v1.isAttr and not v2.isAttr:
            x = mul_div_pow_func((v1.value[0], v2.value[0]), func_operator)
            y = mul_div_pow_func((v1.value[1], v2.value[1]), func_operator)
            z = mul_div_pow_func((v1.value[2], v2.value[2]), func_operator)

            core.delete(NODE)
            return MayaNode(x, y, z)

        if v1.isAttr and v2.isAttr:
            core.PyNode(v1.value) >> attr1
            core.PyNode(v2.value) >> attr2

        elif v1.isAttr and not v2.isAttr:
            core.PyNode(v1.value) >> attr1
            connector(attr2, v2)

        elif not v1.isAttr and v2.isAttr:
            connector(attr1, v1)
            core.PyNode(v2.value) >> attr2

        return MayaNode(NODE.output.name())

    elif v1.type == 'vector' and v2.type == 'single':
        if not v1.isAttr and not v2.isAttr:
            x = mul_div_pow_func((v1.value[0], v2), func_operator)
            y = mul_div_pow_func((v1.value[1], v2), func_operator)
            z = mul_div_pow_func((v1.value[2], v2), func_operator)

            core.delete(NODE)
            return MayaNode(x, y, z)

        if v1.isAttr and v2.isAttr:
            core.PyNode(v1.value) >> attr1
            connector(attr2, v2)

        elif v1.isAttr and not v2.isAttr:
            core.PyNode(v1.value) >> attr1
            connector(attr2, v2)

        elif not v1.isAttr and v2.isAttr:
            connector(attr1, v1)
            connector(attr2, v2)

        return MayaNode(NODE.output.name())

    elif v1.type == 'single' and v2.type == 'vector':
        if not v1.isAttr and not v2.isAttr:
            x = mul_div_pow_func((v2.value[0], v1), func_operator)
            y = mul_div_pow_func((v2.value[1], v1), func_operator)
            z = mul_div_pow_func((v2.value[2], v1), func_operator)

            core.delete(NODE)
            return MayaNode(x, y, z)

        if v1.isAttr and v2.isAttr:
            connector(attr1, v1)
            core.PyNode(v2.value) >> attr2

        elif v1.isAttr and not v2.isAttr:
            connector(attr1, v1)
            connector(attr2, v2)

        elif not v1.isAttr and v2.isAttr:
            connector(attr1, v1)
            core.PyNode(v2.value) >> attr2

        return MayaNode(NODE.output.name())


def cond_func(body):
    v1 = body[0]
    cond = body[1]
    v2 = body[2]

    COND = core.createNode('condition')
    COND.colorIfTrue.set(1, 1, 1)
    COND.colorIfFalse.set(0, 0, 0)

    if cond == '==':
        COND.operation.set(0)
    elif cond == '!=':
        COND.operation.set(1)
    elif cond == '>':
        COND.operation.set(2)
    elif cond == '>=':
        COND.operation.set(3)
    elif cond == '<':
        COND.operation.set(4)
    elif cond == '<=':
        COND.operation.set(5)

    if v1.type == 'single' and v2.type == 'single':
        if not v1.isAttr and not v2.isAttr:
            COND.firstTerm.set(v1.value)
            COND.secondTerm.set(v2.value)

        elif v1.isAttr and v2.isAttr:
            core.PyNode(v1.value) >> COND.firstTerm
            core.PyNode(v2.value) >> COND.secondTerm

        elif not v1.isAttr and v2.isAttr:
            COND.firstTerm.set(v1.value)
            core.PyNode(v2.value) >> COND.secondTerm

        elif v1.isAttr and not v2.isAttr:
            core.PyNode(v1.value) >> COND.firstTerm
            COND.secondTerm.set(v2.value)

        return MayaNode(COND.outColorR.name())

    if v1.type == 'vector' or v2.type == 'vector':
        raise Exception(" Arguments for expression can only be a 'single' type. ")


def ternary_func(body):
    cond = body[0]
    v1 = body[1]
    v2 = body[2]

    if cond.type != 'single':
        raise Exception(" The condition can only have a 'single' type. ")

    COND = core.createNode('condition')
    COND.operation.set(1)  # not equal
    COND.secondTerm.set(0)

    attr1 = COND.colorIfTrue
    attr2 = COND.colorIfFalse

    if not cond.isAttr:
        COND.firstTerm.set(cond.value)
    elif cond.isAttr:
        core.PyNode(cond.value) >> COND.firstTerm

    if v1.type == 'single' and v2.type == 'single':
        if not v1.isAttr and not v2.isAttr:
            COND.colorIfTrueR.set(v1.value)
            COND.colorIfFalseR.set(v2.value)

        elif v1.isAttr and v2.isAttr:
            core.PyNode(v1.value) >> COND.colorIfTrueR
            core.PyNode(v2.value) >> COND.colorIfFalseR

        elif not v1.isAttr and v2.isAttr:
            COND.colorIfTrueR.set(v1.value)
            core.PyNode(v2.value) >> COND.colorIfFalseR

        elif v1.isAttr and not v2.isAttr:
            core.PyNode(v1.value) >> COND.colorIfTrueR
            COND.colorIfFalseR.set(v2.value)

        return MayaNode(COND.outColorR.name())

    if v1.type == 'vector' and v2.type == 'vector':
        if not v1.isAttr and not v2.isAttr:
            connector(attr1, v1)
            connector(attr2, v2)

        elif v1.isAttr and v2.isAttr:
            core.PyNode(v1.value) >> COND.colorIfTrue
            core.PyNode(v2.value) >> COND.colorIfFalse

        elif not v1.isAttr and v2.isAttr:
            connector(attr1, v1)
            core.PyNode(v2.value) >> COND.colorIfFalse

        elif v1.isAttr and not v2.isAttr:
            core.PyNode(v1.value) >> COND.colorIfTrue
            connector(attr2, v2)

    if v1.type == 'vector' and v2.type == 'single':
        if not v1.isAttr and not v2.isAttr:
            connector(attr1, v1)
            connector(attr2, v2)

        elif v1.isAttr and v2.isAttr:
            core.PyNode(v1.value) >> COND.colorIfTrue
            connector(attr2, v2)

        elif not v1.isAttr and v2.isAttr:
            connector(attr1, v1)
            connector(attr2, v2)

        elif v1.isAttr and not v2.isAttr:
            core.PyNode(v1.value) >> COND.colorIfTrue
            connector(attr2, v2)

    if v1.type == 'single' and v2.type == 'vector':
        if not v1.isAttr and not v2.isAttr:
            connector(attr1, v1)
            connector(attr2, v2)

        elif v1.isAttr and v2.isAttr:
            connector(attr1, v1)

            core.PyNode(v2.value) >> COND.colorIfFalse

        elif not v1.isAttr and v2.isAttr:
            connector(attr1, v1)
            core.PyNode(v2.value) >> COND.colorIfFalse

        elif v1.isAttr and not v2.isAttr:
            connector(attr1, v1)
            connector(attr2, v2)

    return MayaNode(COND.outColor.name())


def run_expr(expr_string):
    my_parser = Lark(meta_rules, start='value')
    tree = my_parser.parse(expr_string)
    return MyTransformer().transform(tree)[0]


def abs_func(*args):
    v1 = args[0][0]
    return run_expr('{0} > 0 ? {0} : -{0}'.format(v1.value))


def max_func(*args):
    v1 = args[0][0]
    v2 = args[0][1]
    return run_expr('{0} > {1} ? {0} : {1}'.format(v1.value, v2.value))


def min_func(*args):
    v1 = args[0][0]
    v2 = args[0][1]
    return run_expr('{0} < {1} ? {0} : {1}'.format(v1.value, v2.value))


def vector_func(v1, v2, mode=1, norm=False):
    if not v1.type == 'vector' and not v1.type == 'vector':
        raise Exception("Only vectors")

    NODE = core.createNode('vectorProduct')
    NODE.operation.set(mode)
    NODE.normalizeOutput.set(norm)

    attr1 = NODE.input1
    attr2 = NODE.input2

    if not v1.isAttr and not v2.isAttr:
        connector(attr1, v1)
        connector(attr2, v2)

    elif v1.isAttr and v2.isAttr:
        core.PyNode(v1.value) >> NODE.input1
        core.PyNode(v2.value) >> NODE.input2

    elif v1.isAttr and not v2.isAttr:
        core.PyNode(v1.value) >> NODE.input1
        connector(attr2, v2)

    elif not v1.isAttr and v2.isAttr:
        connector(attr1, v1)
        core.PyNode(v2.value) >> NODE.input2

    return MayaNode(NODE.output.name())


def dot_func(*args):
    values = args[0]
    v1 = values[0]
    v2 = values[1]

    kwargs = args[1]

    norm_ = False

    if 'norm' in kwargs:
        norm_ = bool(kwargs['norm'])

    print v2
    return vector_func(v1, v2, mode=1, norm=norm_)


def cross_func(*args):
    values = args[0]
    v1 = values[0]
    v2 = values[1]

    kwargs = args[1]

    norm_ = False

    if 'norm' in kwargs:
        norm_ = bool(kwargs['norm'])

    return vector_func(v1, v2, mode=2, norm=norm_)


def sin_func(*args):
    values = args[0]
    v1 = values[0]

    kwargs = args[1]

    if v1.type != 'single':
        raise Exception('Sine function can take only single type value')

    MDL = core.createNode("multDoubleLinear")
    MDL.input2.set(2.0)  # degree mode just multiply the input value by 2

    quat = core.createNode("eulerToQuat")
    MDL.output >> quat.inputRotateX
    if v1.isAttr:
        core.PyNode(v1.value) >> MDL.input1
    else:
        MDL.input1.set(v1.value)

    if 'degree' in kwargs:
        param = MayaNode(kwargs['degree'])
        if param.type == 'vector':
            raise Exception('NO VECTORS!!!!')
        else:
            if param.isAttr:
                if not bool(core.PyNode(param.value).get()):
                    MDL.input2.set(2 * 57.2958)  # radian mode
            else:
                if not bool(param.value):
                    MDL.input2.set(2 * 57.2958)  # radian mode

    return MayaNode(quat.outputQuatX.name())


def cos_func(*args):
    values = args[0]
    v1 = values[0]

    kwargs = args[1]

    if v1.type != 'single':
        raise Exception('Sine function can take only single type value')

    MDL = core.createNode("multDoubleLinear")
    MDL.input2.set(2.0)  # degree mode just multiply the input value by 2

    quat = core.createNode("eulerToQuat")
    MDL.output >> quat.inputRotateX
    if v1.isAttr:
        core.PyNode(v1.value) >> MDL.input1
    else:
        MDL.input1.set(v1.value)

    if 'degree' in kwargs:
        param = MayaNode(kwargs['degree'])
        if param.type == 'vector':
            raise Exception('NO VECTORS!!!!')
        else:
            if param.isAttr:
                if not bool(core.PyNode(param.value).get()):
                    MDL.input2.set(2 * 57.2958)  # radian mode
            else:
                if not bool(param.value):
                    MDL.input2.set(2 * 57.2958)  # radian mode

    return MayaNode(quat.outputQuatW.name())


func_dict = {'abs': abs_func, 'max': max_func, 'min': min_func, 'dot': dot_func, 'cross': cross_func, 'sin': sin_func,
             'cos': cos_func}


def function(body):
    func_name = body[0]
    args = filter(lambda x: not isinstance(x, list), body[1])
    kwargs = filter(lambda x: isinstance(x, list), body[1])
    k_dict = {}
    if kwargs:
        for i in kwargs:
            k_dict[i[0]] = i[1].value
    if func_name in func_dict:
        return func_dict[func_name](args, k_dict)


meta_rules = """
    ?value: 
            | expr (expr)*
            | r_val -> single_expr

    expr    : l_val "=" r_val

    l_val   :  node_name -> l_val
    r_val   :  tern

    tern    : cond
            | cond "?" cond ":" cond

    cond    : sum (cond_expr sum)* 

    sum     : prod
            | sum "+" prod  -> sum
            | sum "-" prod  -> sub

    prod    :  pow
            |  prod "*" pow -> mul
            |  prod "/" pow -> div

    pow     : unary
            | pow "**" unary

    unary   : term
            | unary_op term 

    term    : func
            | node_name
            | vector | matrix | const
            | "PI" -> pi
            | "E"  -> e
            | "true" -> true
            | "false" -> false

    func    :  "(" tern ")"   -> parentheses 
            | name "(" [func_expr] ")" 

    func_expr : tern ("," tern)* ("," named_arg)* -> func_expr

    named_arg : name "=" tern

    node_name   : name node_attr

    node_attr   : "." attr_elem ("." attr_elem)*  

    attr_elem   : name [ "[" index "]" ]

    vector: "<" tern ("," tern)+ ">"

    matrix: "[" mtx_expr "]"

    mtx_expr : ( const ("," const)* )?
             | MTX_ARG "=" "(" mtx_val ")" 

    MTX_ARG :  "row" | "column" | "scale" | "pos"    

    mtx_val : const ("," const)*

    index   : int_number -> index

    name    : ATTRIBUTE 
    const   : float_number 
            | int_number

    unary_op   : (UNARY_PLUS | UNARY_MIN)+

    UNARY_MIN  : "-"
    UNARY_PLUS : "+"


    cond_expr : MORE | LESS | EQUAL | NO_EQUAL 
              | MORE_EQUAL | LESS_EQUAL 

    MORE       : ">" 
    LESS       : "<"
    EQUAL      : "=="
    NO_EQUAL   : "!="
    MORE_EQUAL : ">="
    LESS_EQUAL : "<="

    ATTRIBUTE    :  /"*[a-zA-Z]+([a-zA-Z_]|[0-9])*"*/
    int_number   : SIGNED_INT
    float_number : SIGNED_FLOAT    

    %import common.ESCAPED_STRING
    %import common.SIGNED_INT
    %import common.SIGNED_FLOAT
    %import common.WS
    %ignore WS

    """


class MyTransformer(Transformer):
    true = lambda self, _: MayaNode(1)
    false = lambda self, _: MayaNode(0)
    pi = lambda self, _: MayaNode(3.14159265359)
    e = lambda self, _: MayaNode(2.718281828459)

    def expr(self, body):
        expr_func(body)
        return body

    def single_expr(self, body):
        return body

    def l_val(self, body):
        return body[0]

    def r_val(self, body):
        return body[0]

    def tern(self, body):
        if len(body) == 1:
            return body[0]
        else:
            return ternary_func(body)

    def cond(self, body):
        if len(body) == 1:
            return body[0]
        return cond_func(body)

    def cond_expr(self, body):
        return body[0]

    def sum(self, body):
        if len(body) == 1:
            return body[0]
        elif len(body) == 2:
            if not body[0]:
                return body[1]
            elif not body[1]:
                return body[0]
            return sum_sub_func(body, float.__add__)

    def sub(self, body):
        if len(body) == 1:
            return body[0]
        elif len(body) == 2:
            if not body[0]:
                return body[1]
            elif not body[1]:
                return body[0]
            return sum_sub_func(body, float.__sub__)

    def prod(self, body):
        if len(body) == 1:
            return body[0]
        elif len(body) == 2:
            return body

    def term(self, body):
        if body:
            return body[0]

    def pow(self, body):
        if len(body) == 1:
            return body[0]
        return mul_div_pow_func(body, float.__pow__)

    def mul(self, body):
        if not body[0]:
            return body[1]
        elif not body[1]:
            return body[0]
        return mul_div_pow_func(body, float.__mul__)

    def div(self, body):
        if not body[0]:
            return body[1]
        elif not body[1]:
            return body[0]
        return mul_div_pow_func(body, float.__div__)

    def func(self, body):
        return function(body)

    def func_expr(self, body):
        return body

    def named_arg(self, body):
        return body

    def node_name(self, body):
        node_name_str = '%s%s' % (body[0], body[1])
        return MayaNode(node_name_str)

    def node_attr(self, body):
        return ''.join(body)

    def attr_elem(self, body):
        if len(body) == 1:
            return '.' + str(body[0])
        elif len(body) == 2:
            return '.%s[%d]' % (body[0], body[1])

    def parentheses(self, body):
        if body[0]:
            return body[0]

    def attribute(self, body):
        return body[0]

    def index(self, body):
        return int(body[0])

    def name(self, body):
        return str(body[0])

    def vector(self, body):
        if len(body) > 3:
            raise Exception("the vector more than three elements")
        ret = []
        for i in body:
            if i.isAttr:
                ret.append(i)
            else:
                ret.append(i.value)
        return MayaNode(ret)

    def matrix(self, body):
        return body

    def mtx_expr(self, body):
        return body

    def mtx_val(self, body):
        return body

    def const(self, body):
        return MayaNode(body[0])

    def float_number(self, body):
        return float(body[0])

    def int_number(self, body):
        return int(body[0])

    def unary(self, body):
        if not body:
            return
        if len(body) == 1:
            return body[0]
        return unary_func(body)

    def unary_op(self, body):
        if body.count("-") % 2 != 0:
            return -1
        else:
            return 1






