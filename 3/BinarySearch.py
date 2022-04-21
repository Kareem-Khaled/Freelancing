
# You might add additional methods to encapsulate and simplify the operations, but they must be
# thoroughly documented


class Node:
    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None
        
    def __str__(self):
        return ("Node({})".format(self.value)) 

    __repr__ = __str__


class BinarySearchTree:
    '''
        >>> x=BinarySearchTree()
        >>> x.insert('mom')  
        >>> x.insert('omm') 
        >>> x.insert('mmo') 
        >>> x.root          
        Node({'mmo': ['mom', 'omm', 'mmo']})
        >>> x.insert('sat')
        >>> x.insert('kind')
        >>> x.insert('ats') 
        >>> x.root.left
        Node({'ast': ['sat', 'ats']})
        >>> x.root.right is None
        True
        >>> x.root.left.right
        Node({'dikn': ['kind']})
    '''

    def __init__(self):
        self.root = None


    # Modify the insert and _insert methods to allow the operations given in the PDF
    # Document all the modifications done
    def insert(self, value):
        if self.root is None:
            sortedValue = ''.join(sorted(value))
            self.root=Node({sortedValue :[value]})
        else:
            self._insert(self.root, value)


    def _insert(self, node, value):
        key = list(node.value.keys())[0]
        sortedValue = ''.join(sorted(value))
        if(sortedValue == key):
              node.value[sortedValue].append(value)
        elif(sortedValue < key):
            if(node.left == None):
                node.left = Node({sortedValue :[value]})
            else:
                self._insert(node.left, value)
        else:   
            if(node.right == None):
                node.right = Node({sortedValue :[value]})
            else:
                self._insert(node.right, value)


    def isEmpty(self):
        return self.root == None

    @property
    def printInorder(self):
        if self.isEmpty(): 
            return None
        else:
            self._inorderHelper(self.root)
        
    def _inorderHelper(self, node):
        if node is not None:
            self._inorderHelper(node.left) 
            print(node.value, end=' : ') 
            self._inorderHelper(node.right)   

    



class Anagrams:
    '''
        # Verify class has _bst attribute  
        >>> x = Anagrams(5)
        >>> '_bst' in x.__dict__    
        True
        >>> isinstance(x.__dict__.get('_bst'), BinarySearchTree)
        True
        >>> x = Anagrams(5)
        >>> x.create('words_small.txt')
        >>> x.getAnagrams('tap')
        'No match'
        >>> x.getAnagrams('arm')
        'No match'
        >>> x.getAnagrams('rat')
        ['art', 'tar', 'rat']
        >>> x._bst.printInorder
        {'a': ['a']} : {'adns': ['ands', 'sand']} : {'ahms': ['sham', 'hams']} : {'amt': ['tam', 'mat']} : {'arst': ['arts', 'rats', 'star']} : {'arsty': ['artsy']} : {'art': ['art', 'tar', 'rat']} : 
    '''
    
    def __init__(self, word_size):
        self._bst = BinarySearchTree()
        self.max_word_size = word_size



    def create(self, file_name):
       with open(file_name,'r') as f:
        for line in f:
            for word in line.split():
                if len(word) <= self.max_word_size:
                     self._bst.insert(word)
           
    def _count_nodes(self, node): # recursive method to count num of nodes
        if node is None:
            return 0
        return 1 + self._count_nodes(node.left) + self._count_nodes(node.right) 
        
    def _count_words(self, node): # recursive method to count num of words
        if node is None:
            return 0
        key = list(node.value.keys())[0] # key of the dictionary
        return len(node.value[key]) + self._count_words(node.left) + self._count_words(node.right)

    def printResult(self, filename, size): # method to print num of (nodes, words)
        print(f"# Result of the operations ({filename} - {size})")
        print(f"  # {x._count_words(x._bst.root)} words inserted")
        print(f"  # {x._count_nodes(x._bst.root)} nodes in tree")

    def getAnagrams(self, word):
        node = self._bst.root
        sortedWord = ''.join(sorted(word))
        while node != None:
            key = list(node.value.keys())[0]
            if(sortedWord == key):
                return node.value[key]
            elif(sortedWord < key):
                node = node.left
            else:   
                node = node.right
        return 'No match'

if __name__ == '__main__':
#Example-1
    print("========= Example-1 =========")
    x=BinarySearchTree()
    x.insert('mom')  
    x.insert('omm') 
    x.insert('mmo') 
    print(x.root)        
    x.insert('sat')
    x.insert('kind')
    x.insert('ats') 
    print(x.root.left)
    print(x.root.right is None)
    print(x.root.left.right)
#Example-2
    print("\n========= Example-2 =========")
    x = Anagrams(5)
    print('_bst' in x.__dict__ )   
    print(isinstance(x.__dict__.get('_bst'), BinarySearchTree))
    x = Anagrams(5)
    x.create('words_small.txt')
    print(x.getAnagrams('tap'))
    print(x.getAnagrams('arm'))
    print(x.getAnagrams('rat'))
    x._bst.printInorder

#Doc_Section-3_Example-1:
    print("\n\n========= Doc_Section-3_Example-1 =========")
    x = Anagrams(5)
    x.create("words_small.txt")
    x._bst.printInorder

#Doc_Section-3_Example-2:
    print("\n\n========= Doc_Section-3_Example-2 =========")
    x = Anagrams(7)
    x.create("words_small.txt")
    x._bst.printInorder

#Doc_Section-3_Table:
    print("\n\n========= Doc_Section-3_Table =========")
    x = Anagrams(5)
    x.create("words_small.txt")
    x.printResult("words_small.txt",5)
    x = Anagrams(5)
    x.create("words_medium.txt")
    x.printResult("words_medium.txt",5)
    x = Anagrams(6)
    x.create("words_medium.txt")
    x.printResult("words_medium.txt",6)
    x = Anagrams(3)
    x.create("words_large.txt")
    x.printResult("words_large.txt",3)
    x = Anagrams(5)
    x.create("words_large.txt")
    x.printResult("words_large.txt",5)
    x = Anagrams(9)
    x.create("words_large.txt")
    x.printResult("words_large.txt",9)

 #Doc_Section-3_lastExamble:
    print("\n========= Doc_Section-3_lastExamble =========")
    x = Anagrams(5)
    x.create("words_small.txt")
    print(x.getAnagrams('ariel'))
    print(x.getAnagrams('mat'))
    print(x.getAnagrams('art'))
    x = Anagrams(5)
    x.create("words_medium.txt")
    print(x.getAnagrams('sale'))
    print(x.getAnagrams('love'))
    print(x.getAnagrams('mean'))
    x = Anagrams(5)
    x.create("words_large.txt")
    print(x.getAnagrams('mart'))
    print(x.getAnagrams('each'))
    print(x.getAnagrams('oval'))
    print(x.getAnagrams('rat'))