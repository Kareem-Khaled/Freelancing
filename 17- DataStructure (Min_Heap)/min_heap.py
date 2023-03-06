# Name:
# OSU Email:
# Course: CS261 - Data Structures
# Assignment:
# Due Date:
# Description:


from dynamic_array import *

class MinHeapException(Exception):
    """
    Custom exception to be used by MinHeap class
    DO NOT CHANGE THIS CLASS IN ANY WAY
    """
    pass


class MinHeap:
    def __init__(self, start_heap=None):
        """
        Initialize a new MinHeap
        DO NOT CHANGE THIS METHOD IN ANY WAY
        """
        self._heap = DynamicArray()

        # populate MH with initial values (if provided)
        # before using this feature, implement add() method
        if start_heap:
            for node in start_heap:
                self.add(node)

    def __str__(self) -> str:
        """
        Return MH content in human-readable form
        DO NOT CHANGE THIS METHOD IN ANY WAY
        """
        heap_data = [self._heap[i] for i in range(self._heap.length())]
        return 'HEAP ' + str(heap_data)

    def add(self, node: object) -> None:
        self._heap.append(node)
        index = self._heap.length() - 1

        while index > 0:
            parent = (index - 1) // 2
            if self._heap.get_at_index(index) < self._heap.get_at_index(parent):
                # swapping nodes if parent > child
                temp = self._heap.get_at_index(index)
                self._heap.set_at_index(index, self._heap.get_at_index(parent)) 
                self._heap.set_at_index(parent, temp)
                
                index = parent
            else:
                break

    def is_empty(self) -> bool:
        return self._heap.is_empty()

    def get_min(self) -> object:
        if self.is_empty():
            raise MinHeapException
        
        return self._heap.get_at_index(0)

    def remove_min(self) -> object:
        if self.is_empty():
            raise MinHeapException
        
        min_item = self._heap.get_at_index(0)
        index = self._heap.length() - 1
        last_item = self._heap.get_at_index(index)
        self._heap.remove_at_index(index)

        length = self._heap.length()
        if length > 0:
            self._heap.set_at_index(0, last_item)
            _percolate_down(self._heap, 0)

        return min_item

    def build_heap(self, da: DynamicArray) -> None:
        # Create a new DynamicArray object
        self._heap = DynamicArray()

        # Copy the elements from the input DynamicArray into the new object
        for i in range(da.length()):
            self._heap.append(da.get_at_index(i))

        # Heapify the new DynamicArray
        last_parent = (self._heap.length() - 2) // 2
        for i in range(last_parent, -1, -1):
            _percolate_down(self._heap, i)

    def size(self) -> int:
        return self._heap.length()

    def clear(self) -> None:
        self._heap = DynamicArray()


def heapsort(da: DynamicArray) -> None:
    # Build max-heap
    length = da.length()
    for index in range(length // 2 - 1, -1, -1):
        _heapify(da, length, index)
        
    # Sort array
    for index in range(length - 1, 0, -1):
        # Swap root with last element
        temp = da.get_at_index(index)
        da.set_at_index(index, da.get_at_index(0))
        da.set_at_index(0, temp)
        
        # Heapify reduced heap
        _heapify(da, index, 0)

def _heapify(da: DynamicArray, length, index):
    smallest = index
    while True:
        left = 2 * index + 1
        right = 2 * index + 2
        
        # Find smallest element among root and its children
        if left < length and da.get_at_index(left) < da.get_at_index(smallest):
            smallest = left
        if right < length and da.get_at_index(right) < da.get_at_index(smallest):
            smallest = right
        
        # If smallest is not root, swap and update index
        if smallest != index:
            temp = da.get_at_index(index)
            da.set_at_index(index, da.get_at_index(smallest))
            da.set_at_index(smallest, temp)

            index = smallest
            smallest = index
        else:
            break


# It's highly recommended that you implement the following optional          #
# function for percolating elements down the MinHeap. You can call           #
# this from inside the MinHeap class. You may edit the function definition.  #

def _percolate_down(da: DynamicArray, parent: int) -> None:
    while True:
        left_child = (2 * parent) + 1
        right_child = (2 * parent) + 2
        smallest = parent

        if right_child < da.length() and da.get_at_index(right_child) < da.get_at_index(smallest):
            smallest = right_child

        if left_child < da.length() and da.get_at_index(left_child) <= da.get_at_index(smallest):
            smallest = left_child

        if smallest != parent: #swapping
            temp = da.get_at_index(parent)
            da.set_at_index(parent, da.get_at_index(smallest))
            da.set_at_index(smallest, temp)

            parent = smallest
        else:
            break

# ------------------- BASIC TESTING -----------------------------------------


if __name__ == '__main__':

    print("\nPDF - add example 1")
    print("-------------------")
    h = MinHeap()
    print(h, h.is_empty())
    for value in range(300, 200, -15):
        h.add(value)
        print(h)

    print("\nPDF - add example 2")
    print("-------------------")
    h = MinHeap(['fish', 'bird'])
    print(h)
    for value in ['monkey', 'zebra', 'elephant', 'horse', 'bear']:
        h.add(value)
        print(h)

    print("\nPDF - is_empty example 1")
    print("-------------------")
    h = MinHeap([2, 4, 12, 56, 8, 34, 67])
    print(h.is_empty())

    print("\nPDF - is_empty example 2")
    print("-------------------")
    h = MinHeap()
    print(h.is_empty())

    print("\nPDF - get_min example 1")
    print("-----------------------")
    h = MinHeap(['fish', 'bird'])
    print(h)
    print(h.get_min(), h.get_min())

    print("\nPDF - remove_min example 1")
    print("--------------------------")
    h = MinHeap([1, 10, 2, 9, 3, 8, 4, 7, 5, 6])
    while not h.is_empty() and h.is_empty() is not None:
        print(h, end=' ')
        print(h.remove_min())

    print("\nPDF - build_heap example 1")
    print("--------------------------")
    da = DynamicArray([100, 20, 6, 200, 90, 150, 300])
    h = MinHeap(['zebra', 'apple'])
    print(h)
    h.build_heap(da)
    print(h)

    print("--------------------------")
    print("Inserting 500 into input DA:")
    da[0] = 500
    print(da)

    print("Your MinHeap:")
    print(h)
    if h.get_min() == 500:
        print("Error: input array and heap's underlying DA reference same object in memory")

    print("\nPDF - size example 1")
    print("--------------------")
    h = MinHeap([100, 20, 6, 200, 90, 150, 300])
    print(h.size())

    print("\nPDF - size example 2")
    print("--------------------")
    h = MinHeap([])
    print(h.size())

    print("\nPDF - clear example 1")
    print("---------------------")
    h = MinHeap(['monkey', 'zebra', 'elephant', 'horse', 'bear'])
    print(h)
    print(h.clear())
    print(h)

    print("\nPDF - heapsort example 1")
    print("------------------------")
    da = DynamicArray([100, 20, 6, 200, 90, 150, 300])
    print(f"Before: {da}")
    heapsort(da)
    print(f"After:  {da}")

    print("\nPDF - heapsort example 2")
    print("------------------------")
    da = DynamicArray(['monkey', 'zebra', 'elephant', 'horse', 'bear'])
    print(f"Before: {da}")
    heapsort(da)
    print(f"After:  {da}")

