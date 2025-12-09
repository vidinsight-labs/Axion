"""
Sharded Result Cache

Lock contention'ı azaltmak için result cache'i birden fazla shard'a böler.
Her shard'ın kendi lock'u olduğu için paralel erişim mümkündür.

Kullanım:
    cache = ShardedResultCache(shard_count=16, max_size_per_shard=100)
    cache.put("task-123", result)
    result = cache.get("task-123")
"""

import hashlib
from threading import Lock
from typing import Any, Optional, Dict
from collections import OrderedDict


class ShardedResultCache:
    """
    Sharded Result Cache - Lock contention'ı azaltmak için

    Her shard'ın kendi lock'u var, böylece paralel erişim mümkün.
    Task ID hash'ine göre shard seçilir (uniform distribution).

    Özellikler:
    - Lock contention: 1/N (N = shard count)
    - LRU eviction: Her shard'ta ayrı
    - Thread-safe: Her shard için ayrı lock
    """

    def __init__(self, shard_count: int = 16, max_size_per_shard: int = 100):
        """
        Args:
            shard_count: Shard sayısı (power of 2 önerilir: 8, 16, 32)
            max_size_per_shard: Her shard'ın maksimum boyutu
        """
        if shard_count < 1:
            raise ValueError("shard_count en az 1 olmalı")
        if max_size_per_shard < 1:
            raise ValueError("max_size_per_shard en az 1 olmalı")

        self._shard_count = shard_count
        self._max_size_per_shard = max_size_per_shard

        # Her shard: {cache: OrderedDict, lock: Lock}
        self._shards = [
            {
                "cache": OrderedDict(),  # LRU için OrderedDict
                "lock": Lock(),
            }
            for _ in range(shard_count)
        ]

    def _get_shard_index(self, task_id: str) -> int:
        """
        Task ID'den shard index hesapla

        MD5 hash kullanarak uniform distribution sağlar.

        Args:
            task_id: Task ID (UUID string)

        Returns:
            int: Shard index (0 ile shard_count-1 arası)
        """
        # MD5 hash (hızlı ve uniform)
        hash_bytes = hashlib.md5(task_id.encode()).digest()
        # İlk 4 byte'ı integer'a çevir
        hash_int = int.from_bytes(hash_bytes[:4], 'little')
        return hash_int % self._shard_count

    def get(self, task_id: str) -> Optional[Any]:
        """
        Cache'den result al ve sil (pop)

        Args:
            task_id: Task ID

        Returns:
            Result objesi veya None (cache miss)
        """
        shard_idx = self._get_shard_index(task_id)
        shard = self._shards[shard_idx]

        # Sadece ilgili shard'ın lock'unu al
        with shard["lock"]:
            cache = shard["cache"]
            if task_id in cache:
                # OrderedDict.pop() - FIFO sırasına göre
                return cache.pop(task_id)
        return None

    def put(self, task_id: str, result: Any):
        """
        Cache'e result ekle

        LRU eviction: Shard dolarsa en eski item silinir.

        Args:
            task_id: Task ID
            result: Result objesi
        """
        shard_idx = self._get_shard_index(task_id)
        shard = self._shards[shard_idx]

        with shard["lock"]:
            cache = shard["cache"]

            # Ekle (en sona ekler)
            cache[task_id] = result

            # LRU eviction - shard dolu mu?
            if len(cache) > self._max_size_per_shard:
                # En eski item'ı sil (FIFO - ilk eklenen)
                cache.popitem(last=False)

    def size(self) -> int:
        """
        Toplam cache boyutu

        Returns:
            int: Tüm shard'lardaki toplam item sayısı
        """
        total = 0
        for shard in self._shards:
            with shard["lock"]:
                total += len(shard["cache"])
        return total

    def clear(self):
        """Tüm cache'i temizle"""
        for shard in self._shards:
            with shard["lock"]:
                shard["cache"].clear()

    def get_shard_stats(self) -> Dict[int, int]:
        """
        Her shard'ın boyutunu döndür (debugging için)

        Returns:
            Dict: {shard_index: size}
        """
        stats = {}
        for i, shard in enumerate(self._shards):
            with shard["lock"]:
                stats[i] = len(shard["cache"])
        return stats
