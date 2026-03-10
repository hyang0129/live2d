#include "allocator.h"
#include <cstdlib>

void* Allocator::Allocate(const Csm::csmSizeType size)
{
    return malloc(size);
}

void Allocator::Deallocate(void* memory)
{
    free(memory);
}

void* Allocator::AllocateAligned(const Csm::csmSizeType size, const Csm::csmUint32 alignment)
{
    const size_t offset = alignment - 1 + sizeof(void*);
    void* allocation = malloc(size + static_cast<Csm::csmUint32>(offset));
    size_t alignedAddress = reinterpret_cast<size_t>(allocation) + sizeof(void*);
    const size_t shift = alignedAddress % alignment;
    if (shift) alignedAddress += (alignment - shift);
    reinterpret_cast<void**>(alignedAddress)[-1] = allocation;
    return reinterpret_cast<void*>(alignedAddress);
}

void Allocator::DeallocateAligned(void* alignedMemory)
{
    free(static_cast<void**>(alignedMemory)[-1]);
}
