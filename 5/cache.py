
class Node:
    def __init__(self, content):
        self.value = content
        self.next = None

    def __str__(self):
        return ('CONTENT:{}\n'.format(self.value))

    __repr__=__str__


class ContentItem:
    '''
        >>> content1 = ContentItem(1000, 10, "Content-Type: 0", "0xA")
        >>> content2 = ContentItem(1004, 50, "Content-Type: 1", "110010")
        >>> content3 = ContentItem(1005, 18, "Content-Type: 2", "<html><p>'CMPSC132'</p></html>")
        >>> content4 = ContentItem(1005, 18, "another header", "111110")
        >>> hash(content1)
        0
        >>> hash(content2)
        1
        >>> hash(content3)
        2
        >>> hash(content4)
        1
    '''
    def __init__(self, cid, size, header, content):
        self.cid = cid
        self.size = size
        self.header = header
        self.content = content

    def __str__(self):
        return f'CONTENT ID: {self.cid} SIZE: {self.size} HEADER: {self.header} CONTENT: {self.content}'

    __repr__=__str__

    def __eq__(self, other):
        if isinstance(other, ContentItem):
            return self.cid == other.cid and self.size == other.size and self.header == other.header and self.content == other.content
        return False

    def __hash__(self):
        sum = 0
        for ch in self.header:
            sum += ord(ch)
        return sum % 3


class CacheList:
    ''' 
        # An extended version available on Canvas. Make sure you pass this doctest first before running the extended version

        >>> content1 = ContentItem(1000, 10, "Content-Type: 0", "0xA")
        >>> content2 = ContentItem(1004, 50, "Content-Type: 1", "110010")
        >>> content3 = ContentItem(1005, 180, "Content-Type: 2", "<html><p>'CMPSC132'</p></html>")
        >>> content4 = ContentItem(1006, 18, "another header", "111110")
        >>> content5 = ContentItem(1008, 2, "items", "11x1110")
        >>> lst=CacheList(200)
        >>> lst
        REMAINING SPACE:200
        ITEMS:0
        LIST:
        <BLANKLINE>
        >>> lst.put(content1, 'mru')
        'INSERTED: CONTENT ID: 1000 SIZE: 10 HEADER: Content-Type: 0 CONTENT: 0xA'
        >>> lst.put(content2, 'lru')
        'INSERTED: CONTENT ID: 1004 SIZE: 50 HEADER: Content-Type: 1 CONTENT: 110010'
        >>> lst.put(content4, 'mru')
        'INSERTED: CONTENT ID: 1006 SIZE: 18 HEADER: another header CONTENT: 111110'
        >>> lst.put(content5, 'mru')
        'INSERTED: CONTENT ID: 1008 SIZE: 2 HEADER: items CONTENT: 11x1110'
        >>> lst.put(content3, 'lru')
        "INSERTED: CONTENT ID: 1005 SIZE: 180 HEADER: Content-Type: 2 CONTENT: <html><p>'CMPSC132'</p></html>"
        >>> lst.put(content1, 'mru')
        'INSERTED: CONTENT ID: 1000 SIZE: 10 HEADER: Content-Type: 0 CONTENT: 0xA'
        >>> 1006 in lst
        True
        >>> contentExtra = ContentItem(1034, 2, "items", "other content")
        >>> lst.update(1008, contentExtra)
        'UPDATED: CONTENT ID: 1034 SIZE: 2 HEADER: items CONTENT: other content'
        >>> lst
        REMAINING SPACE:170
        ITEMS:3
        LIST:
        [CONTENT ID: 1034 SIZE: 2 HEADER: items CONTENT: other content]
        [CONTENT ID: 1006 SIZE: 18 HEADER: another header CONTENT: 111110]
        [CONTENT ID: 1000 SIZE: 10 HEADER: Content-Type: 0 CONTENT: 0xA]
        <BLANKLINE>
        >>> lst.clear()
        'Cleared cache!'
        >>> lst
        REMAINING SPACE:200
        ITEMS:0
        LIST:
        <BLANKLINE>
    '''
    def __init__(self, size):
        self.head = None
        self.maxSize = size
        self.remainingSpace = size
        self.numItems = 0

    def __str__(self):
        listString = ""
        current = self.head
        while current is not None:
            listString += "[" + str(current.value) + "]\n"
            current = current.next
        return 'REMAINING SPACE:{}\nITEMS:{}\nLIST:\n{}'.format(self.remainingSpace, self.numItems, listString)  

    __repr__=__str__

    def __len__(self):
        return self.numItems
    
    def put(self, content, evictionPolicy):
        if content.cid in self:    
            return f"Content {content.cid} already in cache, insertion not allowed"
        if content.size > self.maxSize:
            return "Insertion not allowed"
        while self.remainingSpace < content.size:
            if evictionPolicy == "lru":
                self.lruEvict()
            else:
                self.mruEvict()
        newNode = Node(content)
        newNode.next = self.head
        self.head = newNode 
        self.numItems += 1
        self.remainingSpace -= content.size
        return f"INSERTED: {content}"
    

    def __contains__(self, cid):
        cur = self.head
        pre = None
        while cur != None:
           if cur.value.cid == cid:
               if pre == None:
                  return True
               newNode = Node(cur.value)
               pre.next = cur.next
               newNode.next = self.head
               self.head = newNode
               return True
           pre = cur
           cur = cur.next
        return False

    def update(self, cid, content):
        if cid not in self or content.size > (self.remainingSpace + self.head.value.size):
            return 'Cache miss!'
        self.remainingSpace += self.head.value.size - content.size
        self.head.value = content
        return f"UPDATED: {self.head.value}"



    def mruEvict(self):
        self.remainingSpace += self.head.value.size
        self.head = self.head.next
        self.numItems -= 1

    
    def lruEvict(self):
        cur = self.head
        pre = None
        while cur.next != None:
           pre = cur
           cur = cur.next
        self.remainingSpace += cur.value.size
        self.numItems -= 1
        if pre:
            pre.next = None
        else:
            self.head = None
    
    def clear(self):
        self.remainingSpace = self.maxSize
        self.numItems = 0
        self.head = None
        return "Cleared cache!"


class Cache:
    """
        # An extended version available on Canvas. Make sure you pass this doctest first before running the extended version

        >>> cache = Cache()
        >>> content1 = ContentItem(1000, 10, "Content-Type: 0", "0xA")
        >>> content2 = ContentItem(1003, 13, "Content-Type: 0", "0xD")
        >>> content3 = ContentItem(1008, 242, "Content-Type: 0", "0xF2")

        >>> content4 = ContentItem(1004, 50, "Content-Type: 1", "110010")
        >>> content5 = ContentItem(1001, 51, "Content-Type: 1", "110011")
        >>> content6 = ContentItem(1007, 155, "Content-Type: 1", "10011011")

        >>> content7 = ContentItem(1005, 18, "Content-Type: 2", "<html><p>'CMPSC132'</p></html>")
        >>> content8 = ContentItem(1002, 14, "Content-Type: 2", "<html><h2>'PSU'</h2></html>")
        >>> content9 = ContentItem(1006, 170, "Content-Type: 2", "<html><button>'Click Me'</button></html>")

        >>> cache.insert(content1, 'lru')
        'INSERTED: CONTENT ID: 1000 SIZE: 10 HEADER: Content-Type: 0 CONTENT: 0xA'
        >>> cache.insert(content2, 'lru')
        'INSERTED: CONTENT ID: 1003 SIZE: 13 HEADER: Content-Type: 0 CONTENT: 0xD'
        >>> cache.insert(content3, 'lru')
        'Insertion not allowed'

        >>> cache.insert(content4, 'lru')
        'INSERTED: CONTENT ID: 1004 SIZE: 50 HEADER: Content-Type: 1 CONTENT: 110010'
        >>> cache.insert(content5, 'lru')
        'INSERTED: CONTENT ID: 1001 SIZE: 51 HEADER: Content-Type: 1 CONTENT: 110011'
        >>> cache.insert(content6, 'lru')
        'INSERTED: CONTENT ID: 1007 SIZE: 155 HEADER: Content-Type: 1 CONTENT: 10011011'

        >>> cache.insert(content7, 'lru')
        "INSERTED: CONTENT ID: 1005 SIZE: 18 HEADER: Content-Type: 2 CONTENT: <html><p>'CMPSC132'</p></html>"
        >>> cache.insert(content8, 'lru')
        "INSERTED: CONTENT ID: 1002 SIZE: 14 HEADER: Content-Type: 2 CONTENT: <html><h2>'PSU'</h2></html>"
        >>> cache.insert(content9, 'lru')
        "INSERTED: CONTENT ID: 1006 SIZE: 170 HEADER: Content-Type: 2 CONTENT: <html><button>'Click Me'</button></html>"
        >>> cache
        L1 CACHE:
        REMAINING SPACE:177
        ITEMS:2
        LIST:
        [CONTENT ID: 1003 SIZE: 13 HEADER: Content-Type: 0 CONTENT: 0xD]
        [CONTENT ID: 1000 SIZE: 10 HEADER: Content-Type: 0 CONTENT: 0xA]
        <BLANKLINE>
        L2 CACHE:
        REMAINING SPACE:45
        ITEMS:1
        LIST:
        [CONTENT ID: 1007 SIZE: 155 HEADER: Content-Type: 1 CONTENT: 10011011]
        <BLANKLINE>
        L3 CACHE:
        REMAINING SPACE:16
        ITEMS:2
        LIST:
        [CONTENT ID: 1006 SIZE: 170 HEADER: Content-Type: 2 CONTENT: <html><button>'Click Me'</button></html>]
        [CONTENT ID: 1002 SIZE: 14 HEADER: Content-Type: 2 CONTENT: <html><h2>'PSU'</h2></html>]
        <BLANKLINE>
        <BLANKLINE>
    """

    def __init__(self):
        self.hierarchy = [CacheList(200), CacheList(200), CacheList(200)]
        self.size = 3
    
    def __str__(self):
        return ('L1 CACHE:\n{}\nL2 CACHE:\n{}\nL3 CACHE:\n{}\n'.format(self.hierarchy[0], self.hierarchy[1], self.hierarchy[2]))
    
    __repr__=__str__


    def clear(self):
        for item in self.hierarchy:
            item.clear()
        return 'Cache cleared!'
    
    def insert(self, content, evictionPolicy):
       return self.hierarchy[hash(content)].put(content, evictionPolicy)


    def __getitem__(self, content):
        if content.cid in self.hierarchy[hash(content)]:
            return content
        return 'Cache miss!'

    def updateContent(self, content):
        return self.hierarchy[hash(content)].update(content.cid, content)


if __name__ == '__main__':
# Hashing-Test
    print("========== Hashing-Test ==========")
    content1 = ContentItem(1000, 10, "Content-Type: 0", "0xA")
    content2 = ContentItem(1004, 50, "Content-Type: 1", "110010")
    content3 = ContentItem(1005, 18, "Content-Type: 2", "<html><p>'CMPSC132'</p></html>")
    content4 = ContentItem(1005, 18, "another header", "111110")
    print(hash(content1))
    print(hash(content2))
    print(hash(content3))
    print(hash(content4))

# CacheList-Test
    print("========== CacheList-Test ==========")
    content1 = ContentItem(1000, 10, "Content-Type: 0", "0xA")
    content2 = ContentItem(1004, 50, "Content-Type: 1", "110010")
    content3 = ContentItem(1005, 180, "Content-Type: 2", "<html><p>'CMPSC132'</p></html>")
    content4 = ContentItem(1006, 18, "another header", "111110")
    content5 = ContentItem(1008, 2, "items", "11x1110")
    lst=CacheList(200)
    print(lst)
    print(lst.put(content1, 'mru'))
    print(lst.put(content2, 'lru'))
    print(lst.put(content4, 'mru'))
    print(lst.put(content5, 'mru'))
    print(lst.put(content3, 'lru'))
    print(lst.put(content1, 'mru'))
    print(1006 in lst)
    contentExtra = ContentItem(1034, 2, "items", "other content")
    print(lst.update(1008, contentExtra))
    print(lst)
    print(lst.clear())
    print(lst)

# Cache-Test
    print("========== Cache-Test ==========")
    cache = Cache()
    content1 = ContentItem(1000, 10, "Content-Type: 0", "0xA")
    content2 = ContentItem(1003, 13, "Content-Type: 0", "0xD")
    content3 = ContentItem(1008, 242, "Content-Type: 0", "0xF2")
    content4 = ContentItem(1004, 50, "Content-Type: 1", "110010")
    content5 = ContentItem(1001, 51, "Content-Type: 1", "110011")
    content6 = ContentItem(1007, 155, "Content-Type: 1", "10011011")
    content7 = ContentItem(1005, 18, "Content-Type: 2", "<html><p>'CMPSC132'</p></html>")
    content8 = ContentItem(1002, 14, "Content-Type: 2", "<html><h2>'PSU'</h2></html>")
    content9 = ContentItem(1006, 170, "Content-Type: 2", "<html><button>'Click Me'</button></html>")
    print(cache.insert(content1, 'lru'))
    print(cache.insert(content2, 'lru'))
    print(cache.insert(content3, 'lru'))
    print(cache.insert(content4, 'lru'))
    print(cache.insert(content5, 'lru'))
    print(cache.insert(content6, 'lru'))
    print(cache.insert(content7, 'lru'))
    print(cache.insert(content8, 'lru'))
    print(cache.insert(content9, 'lru'))
    print(cache)

# EXTENDED DOCTEST FOR CacheList
    print("========== EXTENDED DOCTEST FOR CacheList ==========")
    content1 = ContentItem(1000, 10, "Content-Type: 0", "0xA")
    content2 = ContentItem(1004, 50, "Content-Type: 1", "110010")
    content3 = ContentItem(1005, 180, "Content-Type: 2", "<html><p>'CMPSC132'</p></html>")
    content4 = ContentItem(1006, 18, "another header", "111110")
    content5 = ContentItem(1008, 2, "items", "11x1110")
    lst=CacheList(200)
    print(lst)
    print(lst.put(content1, 'mru'))
    print(lst.put(content2, 'lru'))
    print(lst.put(content4, 'mru'))
    print(lst)
    print(lst.put(content5, 'mru'))
    print(lst)
    print(lst.put(content3, 'lru'))
    print(lst)
    print(lst.put(content1, 'mru'))
    print(lst)
    print(1006 in lst)
    print(lst)
    contentExtra = ContentItem(1034, 2, "items", "other content")
    print(lst.update(3000, contentExtra))
    print(lst.update(1008, contentExtra))
    print(1008 in lst)    
    print(lst)    
    contentExtraDiff = ContentItem(1504, 150, "more items", "other content")    
    print(lst.update(1006, contentExtraDiff))
    print(lst)
    contentExtraMore = ContentItem(2504, 50, "other items", "other content")
    print(lst.update(1000, contentExtraMore))
    print(lst)
    print(lst.clear())
    print(lst)

# EXTENDED DOCTEST FOR Cache
    print("========== EXTENDED DOCTEST FOR Cache ==========")
    cache = Cache()
    content1 = ContentItem(1000, 10, "Content-Type: 0", "0xA")
    content2 = ContentItem(1003, 13, "Content-Type: 0", "0xD")
    content3 = ContentItem(1008, 242, "Content-Type: 0", "0xF2")
    content4 = ContentItem(1004, 50, "Content-Type: 1", "110010")
    content5 = ContentItem(1001, 51, "Content-Type: 1", "110011")
    content6 = ContentItem(1007, 155, "Content-Type: 1", "10011011")
    content7 = ContentItem(1005, 18, "Content-Type: 2", "<html><p>'CMPSC132'</p></html>")
    content8 = ContentItem(1002, 14, "Content-Type: 2", "<html><h2>'PSU'</h2></html>")
    content9 = ContentItem(1006, 170, "Content-Type: 2", "<html><button>'Click Me'</button></html>")
    print(cache.insert(content1, 'lru'))
    print(cache.insert(content2, 'lru'))
    print(cache.insert(content3, 'lru'))
    print(cache.insert(content4, 'lru'))
    print(cache.insert(content5, 'lru'))
    print(cache.insert(content6, 'lru'))
    print(cache.insert(content7, 'lru'))
    print(cache.insert(content8, 'lru'))
    print(cache.insert(content9, 'lru'))
    print(cache)
    print(cache.hierarchy[0].clear())
    print(cache.hierarchy[1].clear())
    print(cache.hierarchy[2].clear())
    print(cache)
    print(cache.insert(content1, 'mru'))
    print(cache.insert(content2, 'mru'))
    print(cache[content1])
    print(cache[content2])
    print(cache[content3])
    print(cache.insert(content5, 'lru'))
    print(cache.insert(content6, 'lru'))
    print(cache.insert(content4, 'lru'))
    print(cache.insert(content7, 'mru'))
    print(cache.insert(content8, 'mru'))
    print(cache.insert(content9, 'mru'))
    print(cache)
    print(cache.clear())
    contentA = ContentItem(2000, 52, "Content-Type: 2", "GET https://www.pro-football-reference.com/boxscores/201802040nwe.htm HTTP/1.1")
    contentB = ContentItem(2001, 76, "Content-Type: 2", "GET https://giphy.com/gifs/93lCI4D0murAszeyA6/html5 HTTP/1.1")
    contentC = ContentItem(2002, 11, "Content-Type: 2", "GET https://media.giphy.com/media/YN7akkfUNQvT1zEBhO/giphy-downsized.gif HTTP/1.1")
    print(cache.insert(contentA, 'lru'))
    print(cache.insert(contentB, 'lru'))
    print(cache.insert(contentC, 'lru'))
    print(cache.hierarchy[2])
    print(cache[contentC])
    print(cache.hierarchy[2])
    print(cache[contentA])
    print(cache.hierarchy[2])
    print(cache[contentC])
    print(cache.hierarchy[2])
    contentD = ContentItem(2002, 11, "Content-Type: 2", "GET https://media.giphy.com/media/YN7akkfUNQvT1zEBhO/giphy-downsized.gif HTTP/1.1")
    print(cache.insert(contentD, 'lru'))
    contentE = ContentItem(2000, 98, "Content-Type: 2", "GET https://www.pro-football-reference.com/boxscores/201801210phi.htm HTTP/1.1")
    print(cache.updateContent(contentE))
    print(cache.hierarchy[2])