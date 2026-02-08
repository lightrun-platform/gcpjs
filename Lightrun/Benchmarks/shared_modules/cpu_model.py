import re
from enum import Enum
from typing import Set, Tuple, List


class CpuModel(Enum):
    """
    Known CPU microarchitectures that can be identified from /proc/cpuinfo.
    
    Each enum value is a tuple of (display_name, vendor_id, required_flags, excluded_flags).
    - required_flags: flags that MUST be present
    - excluded_flags: flags that MUST NOT be present (to distinguish from newer generations)
    
    The identify() class method iterates over all models and returns the first match.
    
    Order matters: more specific models (with more/newer flags) should come before
    less specific ones to ensure correct identification.
    """
    
    # Intel Xeon Scalable Processors (newest to oldest - order matters!)
    # Note: excluded_flags ensure we don't misidentify newer CPUs as older ones
    INTEL_SAPPHIRE_RAPIDS = ("Intel Xeon 4th Gen (Sapphire Rapids)", "GenuineIntel", ["amx_bf16", "amx_int8", "amx_tile"], [])
    INTEL_ICE_LAKE = ("Intel Xeon 3rd Gen (Ice Lake)", "GenuineIntel", ["avx512_vnni", "vaes", "vpclmulqdq", "gfni"], ["amx_bf16"])
    INTEL_COOPER_LAKE = ("Intel Xeon 3rd Gen (Cooper Lake)", "GenuineIntel", ["avx512_bf16"], ["amx_bf16", "gfni"])
    INTEL_CASCADE_LAKE = ("Intel Xeon 2nd Gen (Cascade Lake)", "GenuineIntel", ["avx512_vnni"], ["avx512_bf16", "gfni"])
    INTEL_SKYLAKE = ("Intel Xeon 1st Gen (Skylake)", "GenuineIntel", ["avx512f", "avx512dq", "avx512cd", "avx512bw", "avx512vl"], ["avx512_vnni"])
    INTEL_BROADWELL = ("Intel Xeon v4 (Broadwell)", "GenuineIntel", ["adx", "rdseed", "smap", "avx2"], ["avx512f"])
    INTEL_HASWELL = ("Intel Xeon v3 (Haswell)", "GenuineIntel", ["avx2", "fma", "bmi2"], ["adx"])
    INTEL_IVY_BRIDGE = ("Intel Xeon v2 (Ivy Bridge)", "GenuineIntel", ["avx"], ["avx2"])
    INTEL_LEGACY = ("Intel (Legacy/Unknown)", "GenuineIntel", [], [])
    
    # AMD EPYC Processors (newest to oldest - order matters!)
    # Genoa (Zen 4) has AVX-512 support which Milan (Zen 3) lacks
    AMD_GENOA = ("AMD EPYC 4th Gen (Genoa / Zen 4)", "AuthenticAMD", ["avx512f", "avx512dq", "avx512vl"], [])
    AMD_MILAN = ("AMD EPYC 3rd Gen (Milan / Zen 3)", "AuthenticAMD", ["vaes", "vpclmulqdq", "fsrm"], ["avx512f"])  # Milan doesn't have AVX-512
    AMD_ROME = ("AMD EPYC 2nd Gen (Rome / Zen 2)", "AuthenticAMD", ["clzero", "rdpid", "clwb", "wbnoinvd"], ["vaes"])
    AMD_NAPLES = ("AMD EPYC 1st Gen (Naples / Zen 1)", "AuthenticAMD", ["clzero", "avx2"], ["rdpid"])
    AMD_LEGACY = ("AMD (Legacy/Unknown)", "AuthenticAMD", [], [])
    
    # Unknown - no vendor/flags, used as fallback
    UNKNOWN = ("Unknown", None, [], [])

    def __init__(self, display_name: str, vendor: str | None, required_flags: List[str], excluded_flags: List[str] = None):
        self._display_name = display_name
        self._vendor = vendor
        self._required_flags = required_flags
        self._excluded_flags = excluded_flags if excluded_flags is not None else []

    @property
    def display_name(self) -> str:
        """Human-readable name for this CPU model."""
        return self._display_name
    
    @property
    def vendor(self) -> str | None:
        """Expected vendor_id string (e.g., 'GenuineIntel', 'AuthenticAMD')."""
        return self._vendor
    
    @property
    def required_flags(self) -> List[str]:
        """List of CPU flags that must be present to identify this model."""
        return self._required_flags

    @property
    def excluded_flags(self) -> List[str]:
        """List of CPU flags that must NOT be present to identify this model."""
        return self._excluded_flags

    def matches(self, vendor: str, flags: Set[str]) -> bool:
        """
        Check if this CPU model matches the given vendor and flags.
        
        Args:
            vendor: The vendor_id from /proc/cpuinfo
            flags: Set of CPU flags from /proc/cpuinfo
            
        Returns:
            True if vendor matches, all required flags are present, and no excluded flags are present.
        """
        if self._vendor is None:
            return False
        if vendor != self._vendor:
            return False
        # Check all required flags are present
        if not all(f in flags for f in self._required_flags):
            return False
        # Check no excluded flags are present
        if any(f in flags for f in self._excluded_flags):
            return False
        return True

    def can_be_pinned(self) -> bool:
        """
        Check if this CPU model can be used for CPU pinning.
        
        Models with empty required_flags (LEGACY, UNKNOWN) cannot be pinned
        because they don't have a unique signature.
        """
        return len(self._required_flags) > 0
    
    def get_signature(self) -> Tuple[str, List[str], List[str]] | None:
        """
        Get the (vendor_id, required_flags, excluded_flags) signature for CPU pinning.
        
        Returns:
            Tuple of (vendor_id, required_flags, excluded_flags) or None if not pinnable.
        """
        if not self.can_be_pinned():
            return None
        return self._vendor, self._required_flags, self._excluded_flags

    @classmethod
    def identify(cls, cpuinfo_text: str) -> "CpuModel":
        """
        Factory method to identify CPU model from /proc/cpuinfo text.
        
        Iterates over all enum members in definition order and returns
        the first one that matches. Order matters - more specific models
        should be defined before less specific ones.
        
        Args:
            cpuinfo_text: Contents of /proc/cpuinfo
            
        Returns:
            CpuModel enum member representing the identified CPU
        """
        # Parse Vendor and Flags
        vendor_match = re.search(r'^vendor_id\s+:\s+(.+)$', cpuinfo_text, re.MULTILINE)
        flags_match = re.search(r'^flags\s+:\s+(.+)$', cpuinfo_text, re.MULTILINE)

        if not vendor_match or not flags_match:
            return cls.UNKNOWN

        vendor = vendor_match.group(1).strip()
        flags: Set[str] = set(flags_match.group(1).strip().split())

        # Iterate through all models and return first match
        for model in cls:
            if model == cls.UNKNOWN:
                continue  # Skip UNKNOWN, it's the fallback
            if model.matches(vendor, flags):
                return model

        return cls.UNKNOWN
    
    def __str__(self) -> str:
        """Return the display name for printing."""
        return self._display_name


# Backward compatibility: keep the function interface
def identify_cpu_model(cpuinfo_text: str) -> str:
    """
    Parses /proc/cpuinfo text and attempts to identify the CPU microarchitecture.
    
    This is a convenience wrapper around CpuModel.identify() that returns
    the string value directly.
    
    Args:
        cpuinfo_text: Contents of /proc/cpuinfo
        
    Returns:
        String name of the identified CPU model
    """
    return CpuModel.identify(cpuinfo_text).display_name
