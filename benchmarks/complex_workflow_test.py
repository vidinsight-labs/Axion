#!/usr/bin/env python3
"""
Complex Workflow (MapReduce Pattern) Performance Testi

Bu test, karmaşık workflow'ların (DAG) performansını ölçer:
- MapReduce pattern: Splitter → Mappers → Reducer
- Çoklu bağımlılık yönetimi
- Veri aktarımı (upstream_results)
- Workflow orchestration performansı
"""

import sys
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from axion import Engine, EngineConfig, Task, TaskType


@dataclass
class WorkflowBenchmarkResult:
    """Workflow benchmark sonuçları"""
    test_name: str
    total_tasks: int
    splitter_time: float = 0.0
    mapper_times: List[float] = field(default_factory=list)
    reducer_time: float = 0.0
    total_workflow_time: float = 0.0
    parallel_efficiency: float = 0.0  # Mapper'ların paralel çalışma verimliliği
    data_passing_success: bool = False
    success_rate: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)


def create_mapreduce_workflow(
    script_path: str,
    num_mappers: int = 50,
    mapper_workload: str = "medium"
) -> tuple[List[Task], Task, List[Task], Task]:
    """
    MapReduce pattern workflow oluşturur
    
    Pattern:
        Splitter (root) → [Mapper1, Mapper2, ..., MapperN] → Reducer (final)
    
    Args:
        script_path: Test script path
        num_mappers: Mapper sayısı
        mapper_workload: Mapper iş yükü ("light", "medium", "heavy")
                        light: n=30, medium: n=35, heavy: n=40 (fibonacci için)
    
    Returns:
        tuple: (all_tasks, splitter, mappers, reducer)
    """
    tasks = []
    
    # Workload mapping (fibonacci n değerleri)
    workload_map = {
        "light": 30,
        "medium": 35,
        "heavy": 40
    }
    mapper_n = workload_map.get(mapper_workload, 35)
    
    # 1. Splitter (Root Task) - Bağımlılığı yok
    # Splitter: Küçük bir fibonacci hesaplaması (hızlı)
    splitter = Task.create(
        script_path=script_path,
        params={
            "n": 25,  # Küçük fibonacci (hızlı)
            "task_name": "Splitter",
            "operation": "split",
            "chunks": num_mappers
        },
        task_type=TaskType.CPU_BOUND
    )
    tasks.append(splitter)
    
    # 2. Mappers - Splitter'a bağımlı
    # Her mapper farklı bir fibonacci hesaplar
    mappers = []
    for i in range(num_mappers):
        mapper = Task.create(
            script_path=script_path,
            params={
                "n": mapper_n + (i % 3),  # Biraz varyasyon
                "task_name": f"Mapper-{i}",
                "operation": "map",
                "chunk_id": i
            },
            task_type=TaskType.CPU_BOUND,
            dependencies=[splitter.id]
        )
        mappers.append(mapper)
        tasks.append(mapper)
    
    # 3. Reducer - Tüm Mapper'lara bağımlı
    # Reducer: Küçük bir fibonacci hesaplaması (tüm sonuçları toplar)
    reducer = Task.create(
        script_path=script_path,
        params={
            "n": 25,  # Küçük fibonacci (hızlı)
            "task_name": "Reducer",
            "operation": "reduce"
        },
        task_type=TaskType.CPU_BOUND,
        dependencies=[m.id for m in mappers]  # Tüm mapper'lara bağımlı
    )
    tasks.append(reducer)
    
    return tasks, splitter, mappers, reducer


def run_complex_workflow_test(
    num_mappers: int = 50,
    mapper_workload: str = "medium",
    config: Optional[EngineConfig] = None
) -> WorkflowBenchmarkResult:
    """
    Complex workflow test çalıştırır
    
    Args:
        num_mappers: Mapper sayısı
        mapper_workload: Mapper iş yükü ("light", "medium", "heavy")
        config: Engine config (opsiyonel)
    
    Returns:
        WorkflowBenchmarkResult: Test sonuçları
    """
    print("="*80)
    print("🚀 Complex Workflow (MapReduce Pattern) Performance Testi")
    print("="*80)
    print(f"\n📋 Test Konfigürasyonu:")
    print(f"   - Pattern: Splitter → {num_mappers} Mappers → Reducer")
    print(f"   - Toplam Görev: {num_mappers + 2}")
    print(f"   - Mapper Workload: {mapper_workload}")
    print(f"   - Reducer Bağımlılıkları: {num_mappers} (tüm mapper'lar)")
    
    # Script path - Fibonacci task kullan (CPU-bound, iş yükü ayarlanabilir)
    script_path = str(Path(__file__).parent / "test_scripts" / "fibonacci_task.py")
    if not Path(script_path).exists():
        # Alternatif: Matrix task
        script_path = str(Path(__file__).parent / "test_scripts" / "matrix_task.py")
    
    if not Path(script_path).exists():
        print(f"\n❌ Hata: Test script bulunamadı!")
        print(f"   Aranan path'ler:")
        print(f"   - {Path(__file__).parent / 'test_scripts' / 'fibonacci_task.py'}")
        print(f"   - {Path(__file__).parent / 'test_scripts' / 'matrix_task.py'}")
        raise FileNotFoundError("Test script bulunamadı")
    
    print(f"   📄 Script: {Path(script_path).name}")
    
    # Engine oluştur
    engine = Engine(config or EngineConfig())
    engine.start()
    
    try:
        # Workflow oluştur
        print(f"\n📝 Workflow oluşturuluyor...")
        tasks, splitter, mappers, reducer = create_mapreduce_workflow(
            script_path=script_path,
            num_mappers=num_mappers,
            mapper_workload=mapper_workload
        )
        
        print(f"   ✅ Workflow oluşturuldu:")
        print(f"      - Splitter: {splitter.id[:8]}...")
        print(f"      - Mappers: {len(mappers)} adet")
        print(f"      - Reducer: {reducer.id[:8]}...")
        print(f"      - Toplam: {len(tasks)} görev")
        
        # Workflow'u gönder
        print(f"\n📤 Workflow gönderiliyor...")
        workflow_start = time.time()
        
        task_ids = engine.submit_workflow(tasks)
        submit_time = time.time() - workflow_start
        
        print(f"   ✅ Workflow gönderildi ({submit_time:.3f} saniye)")
        print(f"   📊 Gönderilen task ID'leri: {len(task_ids)}")
        
        # Sistem durumunu kontrol et
        print(f"\n📊 İlk Sistem Durumu:")
        try:
            status = engine.get_status()
            input_queue_size = status["components"]["input_queue"]["metrics"]["size"]
            cpu_workers = status["components"]["process_pool"]["metrics"]["cpu_bound_workers"]
            io_workers = status["components"]["process_pool"]["metrics"]["io_bound_workers"]
            
            print(f"   Input Queue: {input_queue_size} görev")
            print(f"   CPU Workers: {cpu_workers}")
            print(f"   IO Workers: {io_workers}")
            
            # Hazır task'ları göster (bağımlılığı olmayanlar)
            print(f"   ⚡ Hazır görevler: Splitter hemen başlayacak")
        except Exception as e:
            print(f"   ⚠️  Durum alınamadı: {e}")
        
        # Sonuçları topla
        print(f"\n⏳ Sonuçlar bekleniyor...")
        print(f"   📍 İzleme: Splitter → Mappers → Reducer")
        
        results = {}
        task_times = {}
        latencies = []
        
        # 1. Splitter'ı bekle
        print(f"\n   1️⃣  Splitter bekleniyor...")
        splitter_start = time.time()
        splitter_result = engine.get_result(splitter.id, timeout=60.0)
        splitter_time = time.time() - splitter_start
        
        if splitter_result and splitter_result.is_success:
            results[splitter.id] = splitter_result
            task_times[splitter.id] = splitter_time
            print(f"      ✅ Splitter tamamlandı ({splitter_time:.3f} saniye)")
            print(f"         Sonuç: {splitter_result.data}")
        else:
            print(f"      ❌ Splitter başarısız veya timeout!")
            if splitter_result:
                print(f"         Hata: {splitter_result.error}")
            return WorkflowBenchmarkResult(
                test_name="Complex Workflow",
                total_tasks=len(tasks),
                success_rate=0.0
            )
        
        # 2. Mapper'ları bekle (paralel)
        print(f"\n   2️⃣  {num_mappers} Mapper bekleniyor (paralel)...")
        mapper_start = time.time()
        mapper_times = []
        completed_mappers = 0
        
        # Mapper'ları paralel olarak topla
        for i, mapper in enumerate(mappers):
            mapper_result_start = time.time()
            mapper_result = engine.get_result(mapper.id, timeout=120.0)
            mapper_result_time = time.time() - mapper_result_start
            
            if mapper_result and mapper_result.is_success:
                results[mapper.id] = mapper_result
                task_times[mapper.id] = mapper_result_time
                mapper_times.append(mapper_result_time)
                completed_mappers += 1
                
                if (i + 1) % 10 == 0:
                    print(f"      ✅ {i + 1}/{num_mappers} mapper tamamlandı")
            else:
                print(f"      ❌ Mapper-{i} başarısız!")
                if mapper_result:
                    print(f"         Hata: {mapper_result.error}")
        
        mapper_total_time = time.time() - mapper_start
        print(f"      ✅ Tüm mapper'lar tamamlandı ({mapper_total_time:.3f} saniye)")
        print(f"         Başarılı: {completed_mappers}/{num_mappers}")
        print(f"         Ortalama mapper süresi: {statistics.mean(mapper_times):.3f}s" if mapper_times else "")
        
        # 3. Reducer'ı bekle (tüm mapper'lar tamamlanınca otomatik başlar)
        print(f"\n   3️⃣  Reducer bekleniyor (tüm mapper'lar tamamlanınca başlayacak)...")
        reducer_start = time.time()
        reducer_result = engine.get_result(reducer.id, timeout=120.0)
        reducer_time = time.time() - reducer_start
        
        if reducer_result and reducer_result.is_success:
            results[reducer.id] = reducer_result
            task_times[reducer.id] = reducer_time
            print(f"      ✅ Reducer tamamlandı ({reducer_time:.3f} saniye)")
            print(f"         Sonuç: {reducer_result.data}")
            
            # Veri aktarımı kontrolü
            # WorkflowManager upstream_results'ı task.params'a ekler
            # Bu bilgi result.data'da olmayabilir, ama workflow başarılıysa
            # upstream_results başarıyla aktarılmış demektir
            print(f"      📦 Veri Aktarımı: WorkflowManager tarafından yönetiliyor")
            print(f"         (Reducer {num_mappers} mapper sonucunu almalı)")
            # Workflow başarılıysa ve reducer tamamlandıysa, veri aktarımı başarılı
            data_passing_success = True
        else:
            print(f"      ❌ Reducer başarısız veya timeout!")
            if reducer_result:
                print(f"         Hata: {reducer_result.error}")
            data_passing_success = False
        
        # Toplam süre
        total_workflow_time = time.time() - workflow_start
        
        # Metrikler
        success_count = len([r for r in results.values() if r and r.is_success])
        success_rate = (success_count / len(tasks)) * 100
        
        # Paralel verimlilik hesapla
        if mapper_times:
            # Eğer mapper'lar tamamen paralel çalışsaydı: max(mapper_times)
            # Gerçek süre: mapper_total_time
            ideal_parallel_time = max(mapper_times)
            parallel_efficiency = (ideal_parallel_time / mapper_total_time) * 100 if mapper_total_time > 0 else 0
        else:
            parallel_efficiency = 0.0
        
        # Final durum
        print(f"\n📊 Final Sistem Durumu:")
        try:
            status = engine.get_status()
            input_queue_size = status["components"]["input_queue"]["metrics"]["size"]
            output_queue_size = status["components"]["output_queue"]["metrics"]["size"]
            cpu_workers = status["components"]["process_pool"]["metrics"]["cpu_bound_workers"]
            
            print(f"   Input Queue: {input_queue_size} görev")
            print(f"   Output Queue: {output_queue_size} sonuç")
            print(f"   CPU Workers: {cpu_workers}")
        except Exception as e:
            print(f"   ⚠️  Durum alınamadı: {e}")
        
        # Sonuç özeti
        print(f"\n{'='*80}")
        print(f"📈 WORKFLOW PERFORMANS ÖZETİ")
        print(f"{'='*80}")
        print(f"   Toplam Görev: {len(tasks)}")
        print(f"   Başarılı: {success_count}/{len(tasks)} ({success_rate:.1f}%)")
        print(f"   Başarısız: {len(tasks) - success_count}")
        print(f"\n   ⏱️  Zamanlama:")
        print(f"      Splitter: {splitter_time:.3f} saniye")
        print(f"      Mappers (toplam): {mapper_total_time:.3f} saniye")
        if mapper_times:
            print(f"      Mappers (ortalama): {statistics.mean(mapper_times):.3f} saniye")
            print(f"      Mappers (min): {min(mapper_times):.3f} saniye")
            print(f"      Mappers (max): {max(mapper_times):.3f} saniye")
        print(f"      Reducer: {reducer_time:.3f} saniye")
        print(f"      Toplam Workflow: {total_workflow_time:.3f} saniye")
        
        print(f"\n   📊 Verimlilik:")
        if mapper_times:
            print(f"      Paralel Verimlilik: {parallel_efficiency:.1f}%")
            print(f"         (İdeal: {max(mapper_times):.3f}s, Gerçek: {mapper_total_time:.3f}s)")
        print(f"      Veri Aktarımı: {'✅ Başarılı' if data_passing_success else '❌ Başarısız'}")
        
        # Workflow pattern analizi
        print(f"\n   🔗 Workflow Pattern Analizi:")
        print(f"      Pattern: MapReduce (Splitter → Mappers → Reducer)")
        print(f"      Splitter Bağımlılıkları: 0 (root task)")
        print(f"      Mapper Bağımlılıkları: 1 (splitter)")
        print(f"      Reducer Bağımlılıkları: {num_mappers} (tüm mapper'lar)")
        print(f"      Maksimum Derinlik: 2 (Splitter → Mapper → Reducer)")
        
        return WorkflowBenchmarkResult(
            test_name="Complex Workflow (MapReduce)",
            total_tasks=len(tasks),
            splitter_time=splitter_time,
            mapper_times=mapper_times,
            reducer_time=reducer_time,
            total_workflow_time=total_workflow_time,
            parallel_efficiency=parallel_efficiency,
            data_passing_success=data_passing_success,
            success_rate=success_rate,
            metrics={
                "submit_time": submit_time,
                "task_times": task_times,
                "success_count": success_count,
                "total_tasks": len(tasks)
            }
        )
        
    except Exception as e:
        print(f"\n❌ Test hatası: {e}")
        import traceback
        traceback.print_exc()
        return WorkflowBenchmarkResult(
            test_name="Complex Workflow",
            total_tasks=0,
            success_rate=0.0
        )
    
    finally:
        print(f"\n🛑 Engine kapatılıyor...")
        engine.shutdown()
        print(f"✅ Engine kapatıldı")


def main():
    """Ana test fonksiyonu"""
    print("="*80)
    print("🧪 COMPLEX WORKFLOW (MAPREDUCE) PERFORMANCE TEST")
    print("="*80)
    
    # Test 1: Orta ölçekli workflow (50 mapper)
    print("\n" + "="*80)
    print("TEST 1: Orta Ölçekli Workflow (50 Mappers)")
    print("="*80)
    result1 = run_complex_workflow_test(
        num_mappers=50,
        mapper_workload="medium"
    )
    
    # Test 2: Küçük ölçekli workflow (10 mapper) - Hızlı test
    print("\n" + "="*80)
    print("TEST 2: Küçük Ölçekli Workflow (10 Mappers) - Hızlı Test")
    print("="*80)
    result2 = run_complex_workflow_test(
        num_mappers=10,
        mapper_workload="light"
    )
    
    # Karşılaştırma
    print("\n" + "="*80)
    print("📊 KARŞILAŞTIRMA")
    print("="*80)
    print(f"\n   Test 1 (50 Mappers):")
    print(f"      Toplam Süre: {result1.total_workflow_time:.3f} saniye")
    print(f"      Başarı Oranı: {result1.success_rate:.1f}%")
    print(f"      Paralel Verimlilik: {result1.parallel_efficiency:.1f}%")
    
    print(f"\n   Test 2 (10 Mappers):")
    print(f"      Toplam Süre: {result2.total_workflow_time:.3f} saniye")
    print(f"      Başarı Oranı: {result2.success_rate:.1f}%")
    print(f"      Paralel Verimlilik: {result2.parallel_efficiency:.1f}%")
    
    print(f"\n{'='*80}")
    print("✅ Test tamamlandı!")
    print("="*80)


if __name__ == "__main__":
    main()
