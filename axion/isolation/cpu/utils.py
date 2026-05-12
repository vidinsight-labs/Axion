def parse_cpu_range(value: str) -> set[int]:
    """
    "0-1,3,5-7" -> {0, 1, 3, 5, 6, 7}

    Raises:
        ValueError: Geçersiz format veya ters range (örn "3-1")
    """

    cpus: set[int] = set()

    if not value:
        return cpus

    for part in value.split(","):
        part = part.strip()

        if not part:
            continue

        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start = int(start_raw)
            end = int(end_raw)

            if end < start:
                raise ValueError(f"Geçersiz CPU aralığı: {part}")

            cpus.update(range(start, end + 1))
        else:
            cpus.add(int(part))

    return cpus


def format_cpu_range(cpus: set[int]) -> str:
    """
    {0, 1, 2, 5, 6} -> "0-2,5-6"
    """

    if not cpus:
        return ""

    sorted_cpus = sorted(cpus)
    ranges: list[str] = []

    start = prev = sorted_cpus[0]

    for cpu in sorted_cpus[1:]:
        if cpu == prev + 1:
            prev = cpu
            continue

        ranges.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = cpu

    ranges.append(f"{start}-{prev}" if start != prev else str(start))

    return ",".join(ranges)


def count_cpus(value: str) -> int:
    return len(parse_cpu_range(value))


def validate_disjoint(system_cpus: str, axion_cpus: str) -> None:
    system_set = parse_cpu_range(system_cpus)
    axion_set = parse_cpu_range(axion_cpus)

    overlap = system_set & axion_set

    if overlap:
        raise ValueError(
            f"system_cpus ve axion_cpus çakışıyor: {format_cpu_range(overlap)}"
        )


def validate_cpus_string(value: str) -> set[int]:
    """
    Linux cpuset.cpus formatını validate eder ve parse edilmiş set'i döner.

    Geçerli formatlar:
        - "0-3"       -> range
        - "0,2,4"     -> liste
        - "0-1,4-7"   -> mixed
        - "0"         -> tek CPU

    Raises:
        ValueError: Boş, malformed veya ters range.
    """
    if not value or not value.strip():
        raise ValueError("cpus parametresi boş olamaz")

    try:
        cpus = parse_cpu_range(value)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            f"Geçersiz cpus formatı: {value!r}. "
            f"Geçerli format örnekleri: '0-3', '0,2,4', '0-1,4-7'"
        ) from exc

    if not cpus:
        raise ValueError(f"cpus en az 1 CPU içermeli, alınan: {value!r}")

    return cpus
