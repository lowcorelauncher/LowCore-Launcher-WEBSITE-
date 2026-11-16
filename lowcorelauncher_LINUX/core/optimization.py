import ctypes
import os
import sys
from typing import List


class OptimizationEngine:
    """True Multicore CPU & JVM tuning for Minecraft launched through LowCore Client."""

    @staticmethod
    def _memory_info():
        try:
            import psutil
            vm = psutil.virtual_memory()
            return vm.total // (1024 * 1024), vm.available // (1024 * 1024)
        except Exception:
            return None, None

    @staticmethod
    def detect_cpu_count() -> int:
        return max(1, os.cpu_count() or 4)

    @staticmethod
    def detect_physical_cores() -> int:
        try:
            import psutil
            phys = psutil.cpu_count(logical=False)
            if phys:
                return max(1, int(phys))
        except Exception:
            pass
        logical = OptimizationEngine.detect_cpu_count()
        return max(1, logical // 2) if logical >= 4 else logical

    @staticmethod
    def resolve_core_count(multicore_enabled: bool = True, cpu_cores: int = 0) -> int:
        """Resolve active CPU cores passed to -XX:ActiveProcessorCount and OS affinity."""
        total_cores = OptimizationEngine.detect_cpu_count()
        if not multicore_enabled:
            return 1
        try:
            requested = int(cpu_cores or 0)
        except (TypeError, ValueError):
            requested = 0
        if requested > 0:
            return max(1, min(total_cores, requested))
        # Auto: use all cores on 2–4 core CPUs, or leave 1 core free for OS/GPU on larger CPUs
        return max(2, total_cores - 1) if total_cores > 4 else total_cores

    @staticmethod
    def resolve_thread_count(
        multicore_enabled: bool = True,
        cpu_threads: int = 0,
        cpu_cores: int = 0,
    ) -> int:
        """Pick parallel GC / JIT / worker threads paired with the active core count."""
        total_cores = OptimizationEngine.detect_cpu_count()
        active_cores = OptimizationEngine.resolve_core_count(multicore_enabled, cpu_cores)
        if not multicore_enabled:
            return 1
        try:
            requested = int(cpu_threads or 0)
        except (TypeError, ValueError):
            requested = 0
        if requested > 0:
            return max(2, min(total_cores, requested))
        return max(2, active_cores) if total_cores > 1 else 1

    @staticmethod
    def build_high_tier_jvm_args(
        ram_mb: int,
        multicore_enabled: bool = True,
        cpu_threads: int = 0,
        cpu_cores: int = 0,
    ) -> List[str]:
        total_cores = OptimizationEngine.detect_cpu_count()
        active_cores = OptimizationEngine.resolve_core_count(multicore_enabled, cpu_cores)
        threads = OptimizationEngine.resolve_thread_count(multicore_enabled, cpu_threads, cpu_cores)
        conc_threads = max(1, threads // 2)
        jit_threads = max(2, min(8, active_cores)) if multicore_enabled else 1
        forkjoin_parallelism = max(1, active_cores - 1) if multicore_enabled else 1

        total_mb, _ = OptimizationEngine._memory_info()
        if total_mb:
            # Never hand the game more than 75% of the machine's RAM.
            ram_mb = max(1024, min(ram_mb, int(total_mb * 0.75)))

        args = [
            f"-Xms{ram_mb}M",
            f"-Xmx{ram_mb}M",
            "-XX:+UnlockExperimentalVMOptions",
            f"-XX:ActiveProcessorCount={active_cores}",
            "-XX:+UseG1GC",
            f"-XX:ParallelGCThreads={threads}",
            f"-XX:ConcGCThreads={conc_threads}",
            f"-XX:CICompilerCount={jit_threads}",
            "-XX:G1ReservePercent=15",
            "-XX:G1HeapRegionSize=32M",
            "-XX:InitiatingHeapOccupancyPercent=45",
            "-XX:G1MixedGCLiveThresholdPercent=85",
        ]

        if multicore_enabled and active_cores >= 2:
            args += [
                "-XX:+ParallelRefProcEnabled",
                f"-Djava.util.concurrent.ForkJoinPool.common.parallelism={forkjoin_parallelism}",
            ]

        args += [
            f"-Dlowcore.multicore={'true' if multicore_enabled else 'false'}",
            f"-Dlowcore.multicore.cores={active_cores}",
            f"-Dlowcore.worker.threads={threads}",
            f"-Dlowcore.cpu.cores={total_cores}",
            "-XX:+DisableExplicitGC",
            "-XX:+UseStringDeduplication",
            "-XX:MaxGCPauseMillis=20",
            "-Dsun.rmi.dgc.server.gcInterval=2147483646",
            "-Dsun.rmi.dgc.client.gcInterval=2147483646",
            "-Djdk.tls.client.protocols=TLSv1.2,TLSv1.3",
            "-Dlog4j2.formatMsgNoLookups=true",
        ]
        return args

    @staticmethod
    def apply_process_core_affinity(
        pid: int,
        multicore_enabled: bool = True,
        cpu_cores: int = 0,
    ) -> int:
        """Apply OS-level CPU core affinity (and priority on Windows) to the launched JVM PID."""
        if not pid:
            return 0
        total_cores = OptimizationEngine.detect_cpu_count()
        try:
            requested = int(cpu_cores or 0)
        except (TypeError, ValueError):
            requested = 0

        if not multicore_enabled:
            target_count = 1
        elif requested > 0:
            target_count = max(1, min(total_cores, requested))
        else:
            # In Auto multicore mode, unlock all CPU cores at the OS scheduler level
            # while -XX:ActiveProcessorCount guides Java's thread pools cleanly.
            target_count = total_cores

        core_list = list(range(target_count))

        if sys.platform == "win32":
            try:
                PROCESS_SET_INFORMATION = 0x0200
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
                NORMAL_PRIORITY_CLASS = 0x00000020
                k32 = ctypes.windll.kernel32
                handle = k32.OpenProcess(
                    PROCESS_SET_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION,
                    False,
                    int(pid),
                )
                if handle:
                    try:
                        mask = 0
                        for idx in core_list:
                            if idx < 64:
                                mask |= (1 << idx)
                        if mask:
                            k32.SetProcessAffinityMask(handle, ctypes.c_size_t(mask))
                        prio = ABOVE_NORMAL_PRIORITY_CLASS if multicore_enabled else NORMAL_PRIORITY_CLASS
                        k32.SetPriorityClass(handle, prio)
                    finally:
                        k32.CloseHandle(handle)
                return len(core_list)
            except Exception:
                pass

        if hasattr(os, "sched_setaffinity"):
            try:
                os.sched_setaffinity(int(pid), set(core_list))
                return len(core_list)
            except Exception:
                pass

        try:
            import psutil
            psutil.Process(int(pid)).cpu_affinity(core_list)
            return len(core_list)
        except Exception:
            return len(core_list)
