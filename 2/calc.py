
class Node:
    def __init__(self, value):
        self.value = value  
        self.next = None 
    
    def __str__(self):
        return "Node({})".format(self.value) 

    __repr__ = __str__
                          
 
#=============================================== Part I ==============================================

class Stack:
    '''
        >>> x=Stack()
        >>> x.pop()
        >>> x.push(2)
        >>> x.push(4)
        >>> x.push(6)
        >>> x
        Top:Node(6)
        Stack:
        6
        4
        2
        >>> x.pop()
        6
        >>> x
        Top:Node(4)
        Stack:
        4
        2
        >>> len(x)
        2
        >>> x.peek()
        4
    '''
    def __init__(self):
        self.top = None
    
    def __str__(self):
        temp=self.top
        out=[]
        while temp:
            out.append(str(temp.value))
            temp=temp.next
        out='\n'.join(out)
        return ('Top:{}\nStack:\n{}'.format(self.top,out))

    __repr__=__str__


    def isEmpty(self):
        return self.top == None

    def __len__(self): 
        len = 0
        top = self.top
        while top:
            len += 1
            top = top.next
        return len

    def push(self,value):
        newNode = Node(value)
        if self.top == None:
            self.top = newNode
        else:
            newNode.next = self.top
            self.top = newNode
     
    def pop(self):
      if self.isEmpty():
          return
      value = self.top.value
      self.top = self.top.next
      return value

    def peek(self):
        if self.isEmpty():
          return
        return self.top.value


#=============================================== Part II ==============================================

class Calculator:
    def __init__(self):
        self.__expr = None

    @property
    def getExpr(self):
        return self.__expr

    def setExpr(self, new_expr):
        if isinstance(new_expr, str):
            self.__expr=new_expr
        else:
            print('setExpr error: Invalid expression')
            return None

    def _isNumber(self, txt):
        '''
            >>> x=Calculator()
            >>> x._isNumber(' 2.560 ')
            True
            >>> x._isNumber('7 56')
            False
            >>> x._isNumber('2.56p')
            False
        '''
        try:
            float(txt)
            return True
        except ValueError:
            return False

    #check if the precedence of operator is strictly less than top of stack or not
    def _notGreater(self, st, i):
        precedence = {'+':1, '-':1, '*':2, '/':2, '^':3}
        try:
            a = precedence[i]
            b = precedence[st.peek()]
            return True if a <= b else False
        except KeyError:
            return False

    def _isValidExpr(self, txt):
        #check validate of parentheses first
        parentheses = Stack()
        expr = txt.split()
        for i in range(0, len(expr)):
            if expr[i] == '(':
                parentheses.push(expr[i])
            elif expr[i] == ')':
                if parentheses.isEmpty():
                    return False
                parentheses.pop()
        if len(parentheses):
            return False
        #remove all parentheses and check the first and last character
        expr = (txt.replace('(', ' ').replace(')', ' ')).split()
        if (not len(expr)) or (not self._isNumber(expr[0])) or not (self._isNumber(expr[-1])):
                return False
        #operators & numbers checking
        operators = ['+', '-', '*', '/', '^']
        for i in range(1, len(expr)):
            #invalid number or operator
            if (not self._isNumber(expr[i])) and (expr[i] not in operators):
                return False
            #two consecutive numbers or operators
            if self._isNumber(expr[i]) == self._isNumber(expr[i - 1]):
                return False
        return True

    def _getPostfix(self, txt):
        '''
            Required: _getPostfix must create and use a Stack for expression processing
            >>> x=Calculator()
            >>> x._getPostfix('2 ^ 4')
            '2.0 4.0 ^'
            >>> x._getPostfix('2')
            '2.0'
            >>> x._getPostfix('2.1 * 5 + 3 ^ 2 + 1 + 4.45')
            '2.1 5.0 * 3.0 2.0 ^ + 1.0 + 4.45 +'
            >>> x._getPostfix('2 * 5.34 + 3 ^ 2 + 1 + 4')
            '2.0 5.34 * 3.0 2.0 ^ + 1.0 + 4.0 +'
            >>> x._getPostfix('2.1 * 5 + 3 ^ 2 + 1 + 4')
            '2.1 5.0 * 3.0 2.0 ^ + 1.0 + 4.0 +'
            >>> x._getPostfix('( 2.5 )')
            '2.5'
            >>> x._getPostfix ('( ( 2 ) )')
            '2.0'
            >>> x._getPostfix ('2 * ( ( 5 + -3 ) ^ 2 + ( 1 + 4 ) )')
            '2.0 5.0 -3.0 + 2.0 ^ 1.0 4.0 + + *'
            >>> x._getPostfix ('( 2 * ( ( 5 + 3 ) ^ 2 + ( 1 + 4 ) ) )')
            '2.0 5.0 3.0 + 2.0 ^ 1.0 4.0 + + *'
            >>> x._getPostfix ('( ( 2 * ( ( 5 + 3 ) ^ 2 + ( 1 + 4 ) ) ) )')
            '2.0 5.0 3.0 + 2.0 ^ 1.0 4.0 + + *'
            >>> x._getPostfix('2 * ( -5 + 3 ) ^ 2 + ( 1 + 4 )')
            '2.0 -5.0 3.0 + 2.0 ^ * 1.0 4.0 + +'

            # In invalid expressions, you might print an error message, adjust doctest accordingly
            # If you are veryfing the expression in calculate before passing to postfix, this cases are not necessary

            >>> x._getPostfix('2 * 5 + 3 ^ + -2 + 1 + 4')
            >>> x._getPostfix('2 * 5 + 3 ^ - 2 + 1 + 4')
            >>> x._getPostfix('2    5')
            >>> x._getPostfix('25 +')
            >>> x._getPostfix(' 2 * ( 5 + 3 ) ^ 2 + ( 1 + 4 ')
            >>> x._getPostfix(' 2 * ( 5 + 3 ) ^ 2 + ) 1 + 4 (')
            >>> x._getPostfix('2 * 5% + 3 ^ + -2 + 1 + 4')
        '''
        if not self._isValidExpr(txt):
            print("Error: invalid expression")
            return None
        out = ""
        postfixStack = Stack()  # method must use postfixStack to compute the postfix expression
        for i in txt.split():
            #if it's a number, add it to the output
            if self._isNumber(i):
                out += str(float(i)) + ' '
             
            #if the character is an '(', push it to the stack
            elif i  == '(':
                postfixStack.push(i)
 
            #if the character is an ')', pop and output from the stack until and '(' is found
            elif i == ')':
                while postfixStack.peek() != '(':
                    out += postfixStack.pop() + ' '
                else:
                    postfixStack.pop()
 
            #an operator is encountered
            else:
                while (not postfixStack.isEmpty()) and (self._notGreater(postfixStack, i)):
                    out += postfixStack.pop() + ' '
                postfixStack.push(i)

        #pop all the operator from the stack and add it to the output
        while not postfixStack.isEmpty():
            out += postfixStack.pop() + ' '
        return out

    @property
    def calculate(self):
        '''
            calculate must call _getPostfix
            calculate must create and use a Stack to compute the final result as shown in the video lecture
            
            >>> x=Calculator()
            >>> x.setExpr('4 + 3 - 2')
            >>> x.calculate
            5.0
            >>> x.setExpr('-2 + 3.5')
            >>> x.calculate
            1.5
            >>> x.setExpr('4 + 3.65 - 2 / 2')
            >>> x.calculate
            6.65
            >>> x.setExpr('23 / 12 - 223 + 5.25 * 4 * 3423')
            >>> x.calculate
            71661.91666666667
            >>> x.setExpr(' 2 - 3 * 4')
            >>> x.calculate
            -10.0
            >>> x.setExpr('7 ^ 2 ^ 3')
            >>> x.calculate
            5764801.0
            >>> x.setExpr(' 3 * ( ( ( 10 - 2 * 3 ) ) )')
            >>> x.calculate
            12.0
            >>> x.setExpr('8 / 4 * ( 3 - 2.45 * ( 4 - 2 ^ 3 ) ) + 3')
            >>> x.calculate
            28.6
            >>> x.setExpr('2 * ( 4 + 2 * ( 5 - 3 ^ 2 ) + 1 ) + 4')
            >>> x.calculate
            -2.0
            >>> x.setExpr(' 2.5 + 3 * ( 2 + ( 3.0 ) * ( 5 ^ 2 - 2 * 3 ^ ( 2 ) ) * ( 4 ) ) * ( 2 / 8 + 2 * ( 3 - 1 / 3 ) ) - 2 / 3 ^ 2')
            >>> x.calculate
            1442.7777777777778
            

            # In invalid expressions, you might print an error message, but code must return None, adjust doctest accordingly
            >>> x.setExpr(" 4 + + 3 + 2") 
            >>> x.calculate
            >>> x.setExpr("4  3 + 2")
            >>> x.calculate
            >>> x.setExpr('( 2 ) * 10 - 3 * ( 2 - 3 * 2 ) )')
            >>> x.calculate
            >>> x.setExpr('( 2 ) * 10 - 3 * / ( 2 - 3 * 2 )')
            >>> x.calculate
            >>> x.setExpr(' ) 2 ( * 10 - 3 * ( 2 - 3 * 2 ) ')
            >>> x.calculate
            >>> x.setExpr('( 3.5 ) ( 15 )') 
            >>> x.calculate
            >>> x.setExpr('3 ( 5 ) - 15 + 85 ( 12 )') 
            >>> x.calculate
            >>> x.setExpr("( -2 / 6 ) + ( 5 ( ( 9.4 ) ) )") 
            >>> x.calculate
        '''

        if not isinstance(self.__expr,str) or len(self.__expr)<=0:
            print("Argument error in calculate")
            return None

        if not self._isValidExpr(self.__expr):
            return None
        calcStack = Stack()   # method must use calcStack to compute the  expression
        for token in self._getPostfix(self.__expr).split():
            #if it's float push it into stack
            try:
                calcStack.push(float(token))
            #if it's not an float, it must be an operator
            #using ValueError, we can evaluate components of the list other than type float
            except ValueError:
                val1 = calcStack.pop()
                val2 = calcStack.pop()
 
                #operator checking
                if token == '+': val2 += val1
                elif token == '-': val2 -= val1
                elif token == '*': val2 *= val1
                elif token == '/': val2 /= val1
                else : val2 **= val1
                calcStack.push(val2)
        return calcStack.pop()

#=============================================== Part III ==============================================

class AdvancedCalculator:
    '''
        >>> C = AdvancedCalculator()
        >>> C.states == {}
        True
        >>> C.setExpression('a = 5;b = 7 + a;a = 7;c = a + b;c = a * 0;return c')
        >>> C.calculateExpressions() == {'a = 5': {'a': 5.0}, 'b = 7 + a': {'a': 5.0, 'b': 12.0}, 'a = 7': {'a': 7.0, 'b': 12.0}, 'c = a + b': {'a': 7.0, 'b': 12.0, 'c': 19.0}, 'c = a * 0': {'a': 7.0, 'b': 12.0, 'c': 0.0}, '_return_': 0.0}
        True
        >>> C.states == {'a': 7.0, 'b': 12.0, 'c': 0.0}
        True
        >>> C.setExpression('x1 = 5;x2 = 7 * ( x1 - 1 );x1 = x2 - x1;return x2 + x1 ^ 3')
        >>> C.states == {}
        True
        >>> C.calculateExpressions() == {'x1 = 5': {'x1': 5.0}, 'x2 = 7 * ( x1 - 1 )': {'x1': 5.0, 'x2': 28.0}, 'x1 = x2 - x1': {'x1': 23.0, 'x2': 28.0}, '_return_': 12195.0}
        True
        >>> print(C.calculateExpressions())
        {'x1 = 5': {'x1': 5.0}, 'x2 = 7 * ( x1 - 1 )': {'x1': 5.0, 'x2': 28.0}, 'x1 = x2 - x1': {'x1': 23.0, 'x2': 28.0}, '_return_': 12195.0}
        >>> C.states == {'x1': 23.0, 'x2': 28.0}
        True
        >>> C.setExpression('x1 = 5 * 5 + 97;x2 = 7 * ( x1 / 2 );x1 = x2 * 7 / x1;return x1 * ( x2 - 5 )')
        >>> C.calculateExpressions() == {'x1 = 5 * 5 + 97': {'x1': 122.0}, 'x2 = 7 * ( x1 / 2 )': {'x1': 122.0, 'x2': 427.0}, 'x1 = x2 * 7 / x1': {'x1': 24.5, 'x2': 427.0}, '_return_': 10339.0}
        True
        >>> C.states == {'x1': 24.5, 'x2': 427.0}
        True
        >>> C.setExpression('A = 1;B = A + 9;C = A + B;A = 20;D = A + B + C;return D - A')
        >>> C.calculateExpressions() == {'A = 1': {'A': 1.0}, 'B = A + 9': {'A': 1.0, 'B': 10.0}, 'C = A + B': {'A': 1.0, 'B': 10.0, 'C': 11.0}, 'A = 20': {'A': 20.0, 'B': 10.0, 'C': 11.0}, 'D = A + B + C': {'A': 20.0, 'B': 10.0, 'C': 11.0, 'D': 41.0}, '_return_': 21.0}
        True
        >>> C.states == {'A': 20.0, 'B': 10.0, 'C': 11.0, 'D': 41.0}
        True
        >>> C.setExpression('A = 1;B = A + 9;2C = A + B;A = 20;D = A + B + C;return D + A')
        >>> C.calculateExpressions() is None
        True
        >>> C.states == {}
        True
    '''
    def __init__(self):
        self.expressions = ''
        self.states = {}

    def setExpression(self, expression):
        self.expressions = expression
        self.states = {}

    def _isVariable(self, word):
        '''
            >>> C = AdvancedCalculator()
            >>> C._isVariable('volume')
            True
            >>> C._isVariable('4volume')
            False
            >>> C._isVariable('volume2')
            True
            >>> C._isVariable('vol%2')
            False
        '''
        return len(word) and word[0].isalpha() and word.isalnum()
       

    def _replaceVariables(self, expr):
        '''
            >>> C = AdvancedCalculator()
            >>> C.states = {'x1': 23.0, 'x2': 28.0}
            >>> C._replaceVariables('1')
            '1'
            >>> C._replaceVariables('105 + x')
            >>> C._replaceVariables('7 * ( x1 - 1 )')
            '7 * ( 23.0 - 1 )'
            >>> C._replaceVariables('x2 - x1')
            '28.0 - 23.0'
        '''
        expr = expr.split()
        for i in range(0, len(expr)):
            if self._isVariable(expr[i]):
                if expr[i] in self.states:
                    expr[i] = self.states[expr[i]]
                else:
                    return None
        
        return ' '.join(map(str, expr))

    def calculateExpressions(self):
        self.states = {} 
        calcObj = Calculator()     # method must use calcObj to compute each expression
        exprs = self.expressions.split(';')
        out = {}
        for expr in exprs:
            if "return" in expr:
                ret = expr.replace('return', '').strip()
                calcObj.setExpr(self._replaceVariables(ret))
                out["_return_"] = calcObj.calculate
            else:
                vars = expr.split('=')
                a = vars[0].strip()
                if not self._isVariable(a):
                    self.states.clear()
                    return None
                if not a in self.states:
                    self.states[a] = ""

                b = vars[1].strip()
                replaced = self._replaceVariables(b)
                if replaced == None:
                    self.states.clear()
                    return None

                calcObj.setExpr(replaced)
                self.states[a] = calcObj.calculate
                out[expr] = self.states.copy()
        return out
       

if __name__ == '__main__' :
#test-1
 print("====(Stack - test)====")
 x=Stack()
 x.pop()
 x.push(2)
 x.push(4)
 x.push(6)
 print(x)
 x.pop()
 print(x)
 print(len(x))
 print(x.peek())    

#test-2
 print("====(isNumber - test)====")
 x=Calculator()
 print(x._isNumber(' 2.560 '))
 print(x._isNumber('7 56'))
 print(x._isNumber('2.56p'))

#test-3
 print("====(isValidExpr - test)====")
 print('Invalid =========')
 x= Calculator()
 print(x._isValidExpr('4 $ 5'))
 print(x._isValidExpr('4 * + 5'))
 print(x._isValidExpr('4 + '))
 print(x._isValidExpr('4 5'))
 print(x._isValidExpr(') 4 + 5 ('))
 print(x._isValidExpr('( 4 + 5 ) )'))
 print(x._isValidExpr('3(5)'))
 print(x._isValidExpr('4 * - 5'))
 print('not processed =========')

#test-4
 print("====(getPostfix - test)====")
 x=Calculator()
 print(x._getPostfix('2 ^ 4'))
 print(x._getPostfix('2'))
 print(x._getPostfix('2.1 * 5 + 3 ^ 2 + 1 + 4.45'))
 print(x._getPostfix('2 * 5.34 + 3 ^ 2 + 1 + 4'))
 print(x._getPostfix('2.1 * 5 + 3 ^ 2 + 1 + 4'))
 print(x._getPostfix('( 2.5 )'))
 print(x._getPostfix ('( ( 2 ) )'))
 print(x._getPostfix ('2 * ( ( 5 + -3 ) ^ 2 + ( 1 + 4 ) )'))
 print(x._getPostfix ('( 2 * ( ( 5 + 3 ) ^ 2 + ( 1 + 4 ) ) )'))
 print(x._getPostfix ('( ( 2 * ( ( 5 + 3 ) ^ 2 + ( 1 + 4 ) ) ) )'))
 print(x._getPostfix('2 * ( -5 + 3 ) ^ 2 + ( 1 + 4 )'))
 print('Invalid =========')
 print(x._getPostfix('( + )'))
 print(x._getPostfix('2 * 5 + 3 ^ - 2 + 1 + 4'))
 print(x._getPostfix('2    5'))
 print(x._getPostfix('25 +'))
 print(x._getPostfix(' 2 * ( 5 + 3 ) ^ 2 + ( 1 + 4 '))
 print(x._getPostfix(' 2 * ( 5 + 3 ) ^ 2 + ) 1 + 4 ('))
 print(x._getPostfix('2 * 5% + 3 ^ + -2 + 1 + 4'))
 print('not processed =========')

 #test-5
 print("====(calculate - test)====")
 x=Calculator()
 x.setExpr('4 + 3 - 2')
 print(x.calculate)
 x.setExpr('-2 + 3.5')
 print(x.calculate)
 x.setExpr('4 + 3.65 - 2 / 2')
 print(x.calculate)
 x.setExpr('23 / 12 - 223 + 5.25 * 4 * 3423')
 print(x.calculate)
 x.setExpr(' 2 - 3 * 4')
 print(x.calculate)
 x.setExpr('7 ^ ( 2 ^ 3 )')
 print(x.calculate)
 x.setExpr(' 3 * ( ( ( 10 - 2 * 3 ) ) )')
 print(x.calculate)
 x.setExpr('8 / 4 * ( 3 - 2.45 * ( 4 - 2 ^ 3 ) ) + 3')
 print(x.calculate)
 x.setExpr('2 * ( 4 + 2 * ( 5 - 3 ^ 2 ) + 1 ) + 4')
 print(x.calculate)
 x.setExpr(' 2.5 + 3 * ( 2 + ( 3.0 ) * ( 5 ^ 2 - 2 * 3 ^ ( 2 ) ) * ( 4 ) ) * ( 2 / 8 + 2 * ( 3 - 1 / 3 ) ) - 2 / 3 ^ 2')
 print(x.calculate)
 print('Invalid =========')
 x.setExpr(" 4 + + 3 + 2") 
 print(x.calculate) 
 x.setExpr("4  3 + 2")
 print(x.calculate) 
 x.setExpr('( 2 ) * 10 - 3 * ( 2 - 3 * 2 ) )')
 print(x.calculate) 
 x.setExpr('( 2 ) * 10 - 3 * / ( 2 - 3 * 2 )')
 print(x.calculate) 
 x.setExpr(' ) 2 ( * 10 - 3 * ( 2 - 3 * 2 ) ')
 print(x.calculate) 
 x.setExpr('( 3.5 ) ( 15 )') 
 print(x.calculate) 
 x.setExpr('3 ( 5 ) - 15 + 85 ( 12 )') 
 print(x.calculate) 
 x.setExpr("( -2 / 6 ) + ( 5 ( ( 9.4 ) ) )") 
 print(x.calculate) 
 print('not processed =========')


#test-6
 print("====(isVariable - test)====")
 C = AdvancedCalculator()
 print(C._isVariable('volume'))    
 print(C._isVariable('4volume'))
 print(C._isVariable('volume2'))
 print(C._isVariable('vol%2'))   

#test-7
 print("====(replaceVariables - test)====")
 C = AdvancedCalculator()
 C.states = {'x1': 23.0, 'x2': 28.0}
 print(C._replaceVariables('1'))
 print(C._replaceVariables('105 + x'))
 print(C._replaceVariables('7 * ( x1 - 1 )'))
 print(C._replaceVariables('x2 - x1'))

    
#test-8
 print("====(calculateExpressions - doc-sample)====")
 C = AdvancedCalculator()
 C.setExpression('A = 1;B = A + 9;C = A + B;A = 20;D = A + B + C;return D + 2 * B')
 C.states
 print(C.calculateExpressions())
 print(C.states) 
 
#test-9
 print("====(calculateExpressions - test)====")
 C = AdvancedCalculator()
 print(C.states == {})
 C.setExpression('a = 5;b = 7 + a;a = 7;c = a + b;c = a * 0;return c')
 print(C.calculateExpressions() == {'a = 5': {'a': 5.0}, 'b = 7 + a': {'a': 5.0, 'b': 12.0}, 'a = 7': {'a': 7.0, 'b': 12.0}, 'c = a + b': {'a': 7.0, 'b': 12.0, 'c': 19.0}, 'c = a * 0': {'a': 7.0, 'b': 12.0, 'c': 0.0}, '_return_': 0.0})
 print(C.states == {'a': 7.0, 'b': 12.0, 'c': 0.0})
 C.setExpression('x1 = 5;x2 = 7 * ( x1 - 1 );x1 = x2 - x1;return x2 + x1 ^ 3')
 print(C.states == {})
 print(C.calculateExpressions() == {'x1 = 5': {'x1': 5.0}, 'x2 = 7 * ( x1 - 1 )': {'x1': 5.0, 'x2': 28.0}, 'x1 = x2 - x1': {'x1': 23.0, 'x2': 28.0}, '_return_': 12195.0})
 print(C.calculateExpressions())
 print(C.states == {'x1': 23.0, 'x2': 28.0})
 C.setExpression('x1 = 5 * 5 + 97;x2 = 7 * ( x1 / 2 );x1 = x2 * 7 / x1;return x1 * ( x2 - 5 )')
 print(C.calculateExpressions() == {'x1 = 5 * 5 + 97': {'x1': 122.0}, 'x2 = 7 * ( x1 / 2 )': {'x1': 122.0, 'x2': 427.0}, 'x1 = x2 * 7 / x1': {'x1': 24.5, 'x2': 427.0}, '_return_': 10339.0})
 print(C.states == {'x1': 24.5, 'x2': 427.0})
 C.setExpression('A = 1;B = A + 9;C = A + B;A = 20;D = A + B + C;return D - A')
 print(C.calculateExpressions() == {'A = 1': {'A': 1.0}, 'B = A + 9': {'A': 1.0, 'B': 10.0}, 'C = A + B': {'A': 1.0, 'B': 10.0, 'C': 11.0}, 'A = 20': {'A': 20.0, 'B': 10.0, 'C': 11.0}, 'D = A + B + C': {'A': 20.0, 'B': 10.0, 'C': 11.0, 'D': 41.0}, '_return_': 21.0})
 print(C.states == {'A': 20.0, 'B': 10.0, 'C': 11.0, 'D': 41.0})
 C.setExpression('A = 1;B = A + 9;2C = A + B;A = 20;D = A + B + C;return D + A')
 print(C.calculateExpressions() is None)
 print(C.states == {})