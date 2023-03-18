# Course:      CS261 - Data Structures
# Assignment:  6
# Description: Provided data structures necessary to complete the assignment.
#              Please look through this file carefully to see what methods
#              are available and how they're implemented.
#              Don't modify the contents of this file.


# -------------- Used by both HashMaps (SC & OA)  -------------- #

class DynamicArrayException(Exception):
    pass


class DynamicArray:
    """
    Class implementing a Dynamic Array
    Supported methods are:
    append, pop, swap, get_at_index, set_at_index, length
    """

    def __init__(self, arr=None) -> None:
        """Initialize new dynamic array using a list."""
        self._data = arr.copy() if arr else []

    def __iter__(self):
        """
        Disable iterator capability for DynamicArray class
        This means loops and aggregate functions like
        those shown below won't work:

        da = DynamicArray()
        for value in da:        # will not work
        min(da)                 # will not work
        max(da)                 # will not work
        sort(da)                # will not work
        """
        return None

    def __str__(self) -> str:
        """Override string method to provide more readable output."""
        return str(self._data)

    def append(self, value: object) -> None:
        """Add new element at the end of the array."""
        self._data.append(value)

    def pop(self):
        """Remove element from end of the array and return it."""
        return self._data.pop()

    def swap(self, i: int, j: int) -> None:
        """Swap two elements in array given their indices."""
        self._data[i], self._data[j] = self._data[j], self._data[i]

    def get_at_index(self, index: int):
        """Return value of element at a given index."""
        if index < 0 or index >= self.length():
            raise DynamicArrayException
        return self._data[index]

    def __getitem__(self, index: int):
        """Return value of element at a given index using [] syntax."""
        return self.get_at_index(index)

    def set_at_index(self, index: int, value: object) -> None:
        """Set value of element at a given index."""
        if index < 0 or index >= self.length():
            raise DynamicArrayException
        self._data[index] = value

    def __setitem__(self, index: int, value: object) -> None:
        """Set value of element at a given index using [] syntax."""
        self.set_at_index(index, value)

    def length(self) -> int:
        """Return length of array."""
        return len(self._data)


def hash_function_1(key: str) -> int:
    """Sample Hash function #1 to be used with HashMap implementation"""
    hash = 0
    for letter in key:
        hash += ord(letter)
    return hash


def hash_function_2(key: str) -> int:
    """Sample Hash function #2 to be used with HashMap implementation"""
    hash, index = 0, 0
    index = 0
    for letter in key:
        hash += (index + 1) * ord(letter)
        index += 1
    return hash


# --------- For use in Separate Chaining (SC) HashMap  --------- #

class SLNode:
    """
    Singly Linked List node for use in a hash map
    """

    def __init__(self, key: str, value: object, next: "SLNode" = None) -> None:
        """Initialize node given a key and value."""
        self.key = key
        self.value = value
        self.next = next

    def __str__(self) -> str:
        """Override string method to provide more readable output."""
        return '(' + str(self.key) + ': ' + str(self.value) + ')'


class LinkedListIterator:
    """
    Separate iterator class for LinkedList
    """

    def __init__(self, current_node: SLNode) -> None:
        """Initialize the iterator with a node."""
        self._node = current_node

    def __iter__(self) -> "LinkedListIterator":
        """Return the iterator."""
        return self

    def __next__(self) -> SLNode:
        """Obtain next node and advance iterator."""

        if not self._node:
            raise StopIteration

        current_node = self._node
        self._node = self._node.next
        return current_node


class LinkedList:
    """
    Class implementing a Singly Linked List
    Supported methods are: insert, remove, contains, length, iterator
    """

    def __init__(self) -> None:
        """
        Initialize new linked list;
        doesn't use a sentinel and keeps track of its size in a variable.
        """
        self._head = None
        self._size = 0

    def __str__(self) -> str:
        """Override string method to provide more readable output."""
        if not self._head:
            return "SLL []"

        content = str(self._head)
        node = self._head.next
        while node:
            content += ' -> ' + str(node)
            node = node.next
        return 'SLL [' + content + ']'

    def __iter__(self) -> LinkedListIterator:
        """Return an iterator for the list, starting at the head."""
        return LinkedListIterator(self._head)

    def insert(self, key: str, value: object) -> None:
        """Insert new node at front of the list."""
        self._head = SLNode(key, value, self._head)
        self._size += 1

    def remove(self, key: str) -> bool:
        """
        Remove first node with matching key.
        Return True if removal was successful, False otherwise.
        """
        previous, node = None, self._head
        while node:

            if node.key == key:
                if previous:
                    previous.next = node.next
                else:
                    self._head = node.next
                self._size -= 1
                return True

            previous, node = node, node.next
        return False

    def contains(self, key: str) -> SLNode:
        """Return node with matching key, or None if no match"""
        node = self._head
        while node:
            if node.key == key:
                return node
            node = node.next
        return node

    def length(self) -> int:
        """Return the length of the list."""
        return self._size


# ---------- For use in Open Addressing (OA) HashMap  ---------- #

class HashEntry:

    def __init__(self, key: str, value: object) -> None:
        """Initialize an entry for use in a hash map."""
        self.key = key
        self.value = value

        # Set this value to True when you "delete" a HashEntry
        self.is_tombstone = False

    def __str__(self) -> str:
        """Override string method to provide more readable output."""
        return f"K: {self.key} V: {self.value} TS: {self.is_tombstone}"
