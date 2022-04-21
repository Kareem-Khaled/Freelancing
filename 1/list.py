
class Node:
    def __init__(self, value):
        self.value = value  
        self.next = None 
    
    def __str__(self):
        return "Node({})".format(self.value) 

    __repr__ = __str__
                        
                          
class SortedLinkedList:
    '''
        >>> x=SortedLinkedList()
        >>> x.add(8.76)
        >>> x.add(1)
        >>> x.add(1)
        >>> x.add(1)
        >>> x.add(5)
        >>> x.add(3)
        >>> x.add(-7.5)
        >>> x.add(4)
        >>> x.add(9.78)
        >>> x.add(4)
        >>> x
        Head:Node(-7.5)
        Tail:Node(9.78)
        List:-7.5 -> 1 -> 1 -> 1 -> 3 -> 4 -> 4 -> 5 -> 8.76 -> 9.78
        >>> x.replicate()
        Head:Node(-7.5)
        Tail:Node(9.78)
        List:-7.5 -> -7.5 -> 1 -> 1 -> 1 -> 3 -> 3 -> 3 -> 4 -> 4 -> 4 -> 4 -> 4 -> 4 -> 4 -> 4 -> 5 -> 5 -> 5 -> 5 -> 5 -> 8.76 -> 8.76 -> 9.78 -> 9.78
        >>> x
        Head:Node(-7.5)
        Tail:Node(9.78)
        List:-7.5 -> 1 -> 1 -> 1 -> 3 -> 4 -> 4 -> 5 -> 8.76 -> 9.78
        >>> x.removeDuplicates()
        >>> x
        Head:Node(-7.5)
        Tail:Node(9.78)
        List:-7.5 -> 1 -> 3 -> 4 -> 5 -> 8.76 -> 9.78
    '''

    def __init__(self):   # You are not allowed to modify the constructor
        self.head=None
        self.tail=None

    def __str__(self):   # You are not allowed to modify this method
        temp=self.head
        out=[]
        while temp:
            out.append(str(temp.value))
            temp=temp.next
        out=' -> '.join(out) 
        return f'Head:{self.head}\nTail:{self.tail}\nList:{out}'

    __repr__=__str__


    def isEmpty(self):
        return self.head == None

    def __len__(self):
        count=0
        current=self.head
        while current:
            current=current.next
            count+=1
        return count

                
    def add(self, value):
        newNode = Node(value)
        #Empty List
        if self.isEmpty():
            self.head = self.tail = newNode
            return
        
        #insert node in the first (Head)
        if self.head.value >= newNode.value:
            newNode.next = self.head
            self.head = newNode
            return

        #insert node in the last (Tail)
        if self.tail.value <= newNode.value:
            self.tail.next = newNode
            self.tail = newNode
            return
        
        #insert node in the middle
        current = self.head
        while current.next:
            if current.next.value >= newNode.value:
                newNode.next = current.next
                current.next = newNode
                break
            current = current.next             

    def replicate(self):
        if self.isEmpty():
            return None
        replicatedList = SortedLinkedList()
        current = self.head
        while current:
            itr = current.value
            if isinstance(current.value, float) or current.value < 0:
                itr = 2
            elif current.value == 0:
                itr = 1
            while itr > 0:
                replicatedList.add(current.value)
                itr -= 1
            current = current.next             
        print(replicatedList)
        return replicatedList

    def removeDuplicates(self):
        if self.isEmpty():
            return
        current = current2 = self.head
        while current:
            while current and current.value == current2.value:
                current = current.next
            if not current:
                current2.next = None
                self.tail = current2
                break
            current2.next = current
            current2 = current

if __name__ == '__main__':
  #Example : 1
  x = SortedLinkedList()
  x.add(8.76)
  x.add(7)
  x.add(3)
  x.add(-6)
  x.add(58)
  x.add(33)
  x.add(1)
  x.add(-88)
  print(x)        

  #Example : 2
  x = SortedLinkedList()
  x.add(4)
  x.replicate()
  x.add(-23)
  x.add(2)
  x.add(1)
  x.add(20.8)
  print(x)
  x.replicate()
  x.add(-1)
  x.add(0)
  x.add(3)
  x.replicate()
  print(x)
  x.add(2)
  x.replicate()

  #Example : 3
  x = SortedLinkedList()
  x.removeDuplicates()
  print(x)
  x.add(1)
  x.add(1)
  x.add(1)
  x.add(1)
  print(x)
  x.removeDuplicates()
  print(x)
  x.add(1)
  x.add(2)
  x.add(2)
  x.add(2)
  x.add(3)
  x.add(4)
  x.add(5)
  x.add(5)
  x.add(6.7)
  x.add(6.7)
  print(x)
  x.removeDuplicates()
  print(x)