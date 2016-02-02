'''
Allocation of space in data oriented buffers.



This file is part of Data Oriented Python.
Copyright (C) 2016 Elliot Hallmark (permfacture@gmail.com)

Data Oreinted Python is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

Data Oriented Python is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''
from pyglet.graphics.allocation import Allocator, AllocatorMemoryException

DEFAULT_SIZE = 1

class DefraggingAllocator(Allocator):
    '''Deviates from the design decisions of pyglet.graphics.allocation
    by keeping track of allocated regions and allowing for compaction.

    caller is responsible for giving unique id's to entries.'''

    def __init__(self,capacity):
        self._id2selector_dict = {}
        super(DefraggingAllocator,self).__init__(capacity)

    def flush(self):
        '''forget all allocations'''
        self.starts = []
        self.sizes = []
        self._id2selector_dict = {}

    def selector_from_id(self,id):
        return self._id2selector_dict[id]

    def index_from_id(self,id):
        return self._id2selector_dict[id][0]

    def alloc(self,size,id):
        free_start = super(DefraggingAllocator,self).alloc(size)
        self._id2selector_dict[id] = (free_start,size)
        return free_start

    def realloc(self,id,new_size):
        '''Cannot implement without copying essentially the entire code
        of Allocator.realloc, since it potentially calls alloc but it
        doesn't know to change id2selector_dict.

        if it was certain not to call alloc, we could do simply:
        start,size = self.id2selector_dict[id]
        free_start = super(DefraggingAllocator,self).realloc(start,size,new_size)
        self._id2selector_dict[id] = (free_start,new_size)
        '''
        raise NotImplementedError

    def dealloc(self,id):
        start, size = self._id2selector_dict.pop(id)
        super(DefraggingAllocator,self).dealloc(start,size)

    #def get_allocated_regions(self):
    #    #should give same result as base Allocator, but just wanted to
    #    #implement it according to the paradigm of this class
    #    return tuple(zip(*sorted(self._id2selector_dict.values())))

    def defrag(self):
        '''compact items down to fill any free space created by dealloc's
        returns (source_selectors,target_selectors) where selectors are
        slice objects that can be used to move data in real arrays to the 
        defragmented form.  ex:

            for source_sel, target_sel in zip(defrag_allocator.defrag())
                arr[target_sel] = arr[source_sel]
        '''
        free_start = 0 #start at the begining
        source_selectors = []
        target_selectors = []
        id2selector = self._id2selector_dict
        start_getter = lambda x: x[1][0] #sort by starts
        for id, (start, size) in sorted(id2selector.items(), key=start_getter):
          #TODO, accumulate contiguous source areas
          assert start >= free_start
          if start != free_start:
            source_selectors.append(slice(start,start+size,1))
            start = free_start
            target_selectors.append(slice(start,start+size,1))
            id2selector[id] = (start,size)
          free_start = start+size

        return source_selectors, target_selectors

class ArrayAndBroadcastableAllocator(object):
    '''Bundles allocators for buffers where adding a item adds one to the
    broadcastable buffers and a group to the array allocators: ie the
    ArrayAttributes and BroadcastableAttributes from datadomain'''
    def __init__(self):
        self.array_allocator = DefraggingAllocator(0)
        self.broadcast_allocator = DefraggingAllocator(0)
        self.index_from_id = self.broadcast_allocator.index_from_id
        self.selector_from_id = self.array_allocator.selector_from_id

    def flush(self):
        self.array_allocator.flush()
        self.broadcast_allocator.flush()

    def alloc_array(self,id,size):
        '''allocate size for the ArrayAttributes 
        returns array_start'''
        array_start = self.array_allocator.alloc(size,id)
        return array_start

    def set_array_capacity(self,capacity):
        self.array_allocator.set_capacity(capacity)

    def alloc_broadcastable(self,id,size=1):
        '''allocate size for the BroadcastableAttributes
        returns first free index'''
        index = self.broadcast_allocator.alloc(size,id)
        return index

    def set_broadcastable_capacity(self,capacity):
        self.broadcast_allocator.set_capacity(capacity)

    def realloc(self,*args):
        raise NotImplementedError

    def dealloc(self,id):
        self.array_allocator.dealloc(id)
        self.broadcast_allocator.dealloc(id)

    def defrag(self):
        '''defrag both ArrayAttributes and BroadcastableAttributes.
        returns (array_fixers, broadcast_fixers) where the fixers are the
        lists of pairs of slices documented in DefraggingAllocator.defrag'''
        array_fixers = self.array_allocator.defrag()
        broadcast_fixers = self.broadcast_allocator.defrag()
        return (array_fixers, broadcast_fixers)