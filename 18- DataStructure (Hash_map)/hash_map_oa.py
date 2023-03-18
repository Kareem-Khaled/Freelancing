# Name:
# OSU Email:
# Course: CS261 - Data Structures
# Assignment:
# Due Date:
# Description:

from a6_include import (DynamicArray, DynamicArrayException, HashEntry,
                        hash_function_1, hash_function_2)


class HashMap:
    def __init__(self, capacity: int, function) -> None:
        """
        Initialize new HashMap that uses
        quadratic probing for collision resolution
        DO NOT CHANGE THIS METHOD IN ANY WAY
        """
        self._buckets = DynamicArray()

        # capacity must be a prime number
        self._capacity = self._next_prime(capacity)
        for _ in range(self._capacity):
            self._buckets.append(None)

        self._hash_function = function
        self._size = 0

    def __str__(self) -> str:
        """
        Override string method to provide more readable output
        DO NOT CHANGE THIS METHOD IN ANY WAY
        """
        out = ''
        for i in range(self._buckets.length()):
            out += str(i) + ': ' + str(self._buckets[i]) + '\n'
        return out

    def _next_prime(self, capacity: int) -> int:
        """
        Increment from given number to find the closest prime number
        DO NOT CHANGE THIS METHOD IN ANY WAY
        """
        if capacity % 2 == 0:
            capacity += 1

        while not self._is_prime(capacity):
            capacity += 2

        return capacity

    @staticmethod
    def _is_prime(capacity: int) -> bool:
        """
        Determine if given integer is a prime number and return boolean
        DO NOT CHANGE THIS METHOD IN ANY WAY
        """
        if capacity == 2 or capacity == 3:
            return True

        if capacity == 1 or capacity % 2 == 0:
            return False

        factor = 3
        while factor ** 2 <= capacity:
            if capacity % factor == 0:
                return False
            factor += 2

        return True

    def get_size(self) -> int:
        """
        Return size of map
        DO NOT CHANGE THIS METHOD IN ANY WAY
        """
        return self._size

    def get_capacity(self) -> int:
        """
        Return capacity of map
        DO NOT CHANGE THIS METHOD IN ANY WAY
        """
        return self._capacity

    # ------------------------------------------------------------------ #

    def put(self, key: str, value: object) -> None:
        capacity = self.get_capacity()

        # if load factor >= 0.5, double the capacity
        if self.table_load() >= 0.5:
            self.resize_table(capacity * 2)
            capacity = self.get_capacity()

        # getting the target index
        index, add_new = 0, True
        hash_key = self._hash_function(key) % capacity
        hash_entry = self._buckets.get_at_index(hash_key)

        while hash_entry != None:
            # if the item is deleted, break
            if hash_entry.is_tombstone == True:
                break
            # if the same key founded, update
            if hash_entry.key == key:
                add_new = False
                hash_entry.value = value
                break
            index += 1
            hash_key = self._hash_function(key) % capacity
            hash_key = (hash_key + index * index) % capacity
            hash_entry = self._buckets.get_at_index(hash_key)

        if add_new:
            self._size += 1
            self._buckets.set_at_index(hash_key, HashEntry(key, value))


    def table_load(self) -> float:
        # return table load factor
        return self.get_size() / self.get_capacity()

    def empty_buckets(self) -> int:
       # return the number of empty buckets
       return self.get_capacity() - self.get_size()

    def _rehash(self, new_capacity):
        # moving items to new bigger hash map
        capacity, temp_buckets = self.get_capacity(), self._buckets
        self._size = 0
        self._capacity = new_capacity
        self._buckets = DynamicArray()

        for _ in range(new_capacity):
            self._buckets.append(None)

        for index in range(capacity):
            hash_entry = temp_buckets.get_at_index(index)

            if hash_entry == None or hash_entry.is_tombstone:
                continue

            self.put(hash_entry.key, hash_entry.value)

    def resize_table(self, new_capacity: int) -> None:
        # check if the new_capacity is valid
        if new_capacity < self.get_size():
            return

        # new_capacity should be prime        
        if not self._is_prime(new_capacity):
            new_capacity = self._next_prime(new_capacity)

        self._rehash(new_capacity)
        
    def get(self, key: str) -> object:
        # getting the target index
        index, capacity = 0, self.get_capacity()
        hash_key = self._hash_function(key) % capacity
        hash_entry = self._buckets.get_at_index(hash_key)

        while hash_entry != None:
            if hash_entry.key == key and hash_entry.is_tombstone == False:
                return hash_entry.value
            index += 1
            hash_key = self._hash_function(key) % capacity
            hash_key = (hash_key + index * index) % capacity
            hash_entry = self._buckets.get_at_index(hash_key)

        return None

    def contains_key(self, key: str) -> bool:
        # getting the target index
        index, capacity = 0, self.get_capacity()
        hash_key = self._hash_function(key) % capacity
        hash_entry = self._buckets.get_at_index(hash_key)

        while hash_entry != None:
            # if the key exists and not deleted, return True
            if hash_entry.key == key and hash_entry.is_tombstone == False:
                return True
            index += 1
            hash_key = self._hash_function(key) % capacity
            hash_key = (hash_key + index * index) % capacity
            hash_entry = self._buckets.get_at_index(hash_key)

        return False

    def remove(self, key: str) -> None:
        # getting the target index
        index, capacity = 0, self.get_capacity()
        hash_key = self._hash_function(key) % capacity
        hash_entry = self._buckets.get_at_index(hash_key)

        while hash_entry != None:
            # if the key exists and not deleted, delete it
            if hash_entry.key == key and hash_entry.is_tombstone == False:
                self._size -= 1
                hash_entry.is_tombstone = True
                return
            index += 1
            hash_key = self._hash_function(key) % capacity
            hash_key = (hash_key + index * index) % capacity
            hash_entry = self._buckets.get_at_index(hash_key)

    def clear(self) -> None:
        # clear all the hash map
        self._size = 0
        for index in range(self.get_capacity()):
            self._buckets.set_at_index(index, None)

    def get_keys_and_values(self) -> DynamicArray:
        result, capacity = DynamicArray(), self.get_capacity()
        for index in range(capacity):
            hash_entry = self._buckets.get_at_index(index)
            if hash_entry != None and hash_entry.is_tombstone == False:
                result.append((hash_entry.key, hash_entry.value))
        
        return result

    def __iter__(self):
        self._current_index = 0
        return self

    def __next__(self):
        while self._current_index < self.get_capacity():
            hash_entry = self._buckets.get_at_index(self._current_index)
            if hash_entry != None and hash_entry.is_tombstone == False:
                self._current_index += 1
                return hash_entry
            self._current_index += 1
        raise StopIteration

# ------------------- BASIC TESTING ---------------------------------------- #

if __name__ == "__main__":
    print("\nPDF - put example 1")
    print("-------------------")
    m = HashMap(53, hash_function_1)
    for i in range(150):
        m.put('str' + str(i), i * 100)
        if i % 25 == 24:
            print(m.empty_buckets(), round(m.table_load(), 2), m.get_size(), m.get_capacity())

    print("\nPDF - put example 2")
    print("-------------------")
    m = HashMap(41, hash_function_2)
    for i in range(50):
        m.put('str' + str(i // 3), i * 100)
        if i % 10 == 9:
            print(m.empty_buckets(), round(m.table_load(), 2), m.get_size(), m.get_capacity())

    print("\nPDF - table_load example 1")
    print("--------------------------")
    m = HashMap(101, hash_function_1)
    print(round(m.table_load(), 2))
    m.put('key1', 10)
    print(round(m.table_load(), 2))
    m.put('key2', 20)
    print(round(m.table_load(), 2))
    m.put('key1', 30)
    print(round(m.table_load(), 2))

    print("\nPDF - table_load example 2")
    print("--------------------------")
    m = HashMap(53, hash_function_1)
    for i in range(50):
        m.put('key' + str(i), i * 100)
        if i % 10 == 0:
            print(round(m.table_load(), 2), m.get_size(), m.get_capacity())

    print("\nPDF - empty_buckets example 1")
    print("-----------------------------")
    m = HashMap(101, hash_function_1)
    print(m.empty_buckets(), m.get_size(), m.get_capacity())
    m.put('key1', 10)
    print(m.empty_buckets(), m.get_size(), m.get_capacity())
    m.put('key2', 20)
    print(m.empty_buckets(), m.get_size(), m.get_capacity())
    m.put('key1', 30)
    print(m.empty_buckets(), m.get_size(), m.get_capacity())
    m.put('key4', 40)
    print(m.empty_buckets(), m.get_size(), m.get_capacity())

    print("\nPDF - empty_buckets example 2")
    print("-----------------------------")
    m = HashMap(53, hash_function_1)
    for i in range(150):
        m.put('key' + str(i), i * 100)
        if i % 30 == 0:
            print(m.empty_buckets(), m.get_size(), m.get_capacity())

    print("\nPDF - resize example 1")
    print("----------------------")
    m = HashMap(23, hash_function_1)
    m.put('key1', 10)
    print(m.get_size(), m.get_capacity(), m.get('key1'), m.contains_key('key1'))
    m.resize_table(30)
    print(m.get_size(), m.get_capacity(), m.get('key1'), m.contains_key('key1'))

    print("\nPDF - resize example 2")
    print("----------------------")
    m = HashMap(79, hash_function_2)
    keys = [i for i in range(1, 1000, 13)]
    for key in keys:
        m.put(str(key), key * 42)
    print(m.get_size(), m.get_capacity())

    for capacity in range(111, 1000, 117):
        m.resize_table(capacity)

        if m.table_load() > 0.5:
            print(f"Check that the load factor is acceptable after the call to resize_table().\n"
                  f"Your load factor is {round(m.table_load(), 2)} and should be less than or equal to 0.5")

        m.put('some key', 'some value')
        result = m.contains_key('some key')
        m.remove('some key')

        for key in keys:
            # all inserted keys must be present
            result &= m.contains_key(str(key))
            # NOT inserted keys must be absent
            result &= not m.contains_key(str(key + 1))
        print(capacity, result, m.get_size(), m.get_capacity(), round(m.table_load(), 2))

    print("\nPDF - get example 1")
    print("-------------------")
    m = HashMap(31, hash_function_1)
    print(m.get('key'))
    m.put('key1', 10)
    print(m.get('key1'))

    print("\nPDF - get example 2")
    print("-------------------")
    m = HashMap(151, hash_function_2)
    for i in range(200, 300, 7):
        m.put(str(i), i * 10)
    print(m.get_size(), m.get_capacity())
    for i in range(200, 300, 21):
        print(i, m.get(str(i)), m.get(str(i)) == i * 10)
        print(i + 1, m.get(str(i + 1)), m.get(str(i + 1)) == (i + 1) * 10)

    print("\nPDF - contains_key example 1")
    print("----------------------------")
    m = HashMap(11, hash_function_1)
    print(m.contains_key('key1'))
    m.put('key1', 10)
    m.put('key2', 20)
    m.put('key3', 30)
    print(m.contains_key('key1'))
    print(m.contains_key('key4'))
    print(m.contains_key('key2'))
    print(m.contains_key('key3'))
    m.remove('key3')
    print(m.contains_key('key3'))

    print("\nPDF - contains_key example 2")
    print("----------------------------")
    m = HashMap(79, hash_function_2)
    keys = [i for i in range(1, 1000, 20)]
    for key in keys:
        m.put(str(key), key * 42)

    print(m.get_size(), m.get_capacity())
    result = True
    for key in keys:
        # all inserted keys must be present
        result &= m.contains_key(str(key))
        # NOT inserted keys must be absent
        result &= not m.contains_key(str(key + 1))
    print(result)

    print("\nPDF - remove example 1")
    print("----------------------")
    m = HashMap(53, hash_function_1)
    print(m.get('key1'))
    m.put('key1', 10)
    print(m.get('key1'))
    m.remove('key1')
    print(m.get('key1'))
    m.remove('key4')

    print("\nPDF - clear example 1")
    print("---------------------")
    m = HashMap(101, hash_function_1)
    print(m.get_size(), m.get_capacity())
    m.put('key1', 10)
    m.put('key2', 20)
    m.put('key1', 30)
    print(m.get_size(), m.get_capacity())
    m.clear()
    print(m.get_size(), m.get_capacity())

    print("\nPDF - clear example 2")
    print("---------------------")
    m = HashMap(53, hash_function_1)
    print(m.get_size(), m.get_capacity())
    m.put('key1', 10)
    print(m.get_size(), m.get_capacity())
    m.put('key2', 20)
    print(m.get_size(), m.get_capacity())
    m.resize_table(100)
    print(m.get_size(), m.get_capacity())
    m.clear()
    print(m.get_size(), m.get_capacity())

    print("\nPDF - get_keys_and_values example 1")
    print("------------------------")
    m = HashMap(11, hash_function_2)
    for i in range(1, 6):
        m.put(str(i), str(i * 10))
    print(m.get_keys_and_values())

    m.resize_table(2)
    print(m.get_keys_and_values())

    m.put('20', '200')
    m.remove('1')
    m.resize_table(12)
    print(m.get_keys_and_values())

    print("\nPDF - __iter__(), __next__() example 1")
    print("---------------------")
    m = HashMap(10, hash_function_1)
    for i in range(5):
        m.put(str(i), str(i * 10))
    print(m)
    for item in m:
        print('K:', item.key, 'V:', item.value)

    print("\nPDF - __iter__(), __next__() example 2")
    print("---------------------")
    m = HashMap(10, hash_function_2)
    for i in range(5):
        m.put(str(i), str(i * 24))
    m.remove('0')
    m.remove('4')
    print(m)
    for item in m:
        print('K:', item.key, 'V:', item.value)