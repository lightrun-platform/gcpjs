import unittest
from pathlib import Path
import sys

# Add parent directories to path
benchmarks_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(benchmarks_dir))
sys.path.insert(0, str(benchmarks_dir.parent))

from Lightrun.Benchmarks.shared_modules.cpu_model import CpuModel, identify_cpu_model


class TestCpuModel(unittest.TestCase):
    """Tests for the CpuModel enum and identify_cpu_model function."""

    # Sample /proc/cpuinfo snippets for different CPU architectures
    AMD_MILAN_CPUINFO = """
processor	: 0
vendor_id	: AuthenticAMD
cpu family	: 25
model		: 1
model name	: AMD EPYC 7B13
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl nonstop_tsc cpuid extd_apicid aperfmperf tsc_known_freq pni pclmulqdq monitor ssse3 fma cx16 pcid sse4_1 sse4_2 x2apic movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy cr8_legacy abm sse4a misalignsse 3dnowprefetch osvw topoext invpcid_single ssbd ibrs ibpb stibp vmmcall fsgsbase tsc_adjust bmi1 avx2 smep bmi2 erms invpcid rdseed adx smap clflushopt clwb sha_ni xsaveopt xsavec xgetbv1 xsaves clzero xsaveerptr rdpru arat npt nrip_save tsc_scale vmcb_clean flushbyasid decodeassists pausefilter pfthreshold v_vmsave_vmload umip vaes vpclmulqdq rdpid fsrm
"""

    AMD_ROME_CPUINFO = """
processor	: 0
vendor_id	: AuthenticAMD
cpu family	: 23
model		: 49
model name	: AMD EPYC 7B12
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl nonstop_tsc cpuid extd_apicid aperfmperf tsc_known_freq pni pclmulqdq monitor ssse3 fma cx16 pcid sse4_1 sse4_2 x2apic movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy cr8_legacy abm sse4a misalignsse 3dnowprefetch osvw topoext invpcid_single ssbd ibrs ibpb stibp vmmcall fsgsbase tsc_adjust bmi1 avx2 smep bmi2 erms invpcid rdseed adx smap clflushopt clwb sha_ni xsaveopt xsavec xgetbv1 xsaves clzero xsaveerptr rdpru arat npt nrip_save tsc_scale vmcb_clean flushbyasid decodeassists pausefilter pfthreshold v_vmsave_vmload umip rdpid wbnoinvd
"""

    AMD_GENOA_CPUINFO = """
processor	: 0
vendor_id	: AuthenticAMD
cpu family	: 25
model		: 17
model name	: AMD EPYC 9654
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl nonstop_tsc cpuid extd_apicid aperfmperf tsc_known_freq pni pclmulqdq monitor ssse3 fma cx16 pcid sse4_1 sse4_2 x2apic movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy cr8_legacy abm sse4a misalignsse 3dnowprefetch osvw topoext invpcid_single ssbd ibrs ibpb stibp vmmcall fsgsbase tsc_adjust bmi1 avx2 smep bmi2 erms invpcid rdseed adx smap clflushopt clwb sha_ni xsaveopt xsavec xgetbv1 xsaves clzero xsaveerptr rdpru arat npt nrip_save tsc_scale vmcb_clean flushbyasid decodeassists pausefilter pfthreshold v_vmsave_vmload umip vaes vpclmulqdq rdpid fsrm avx512f avx512dq avx512ifma avx512cd avx512bw avx512vl avx512_bf16 avx512vbmi avx512_vbmi2 avx512_vnni avx512_bitalg avx512_vpopcntdq
"""

    INTEL_CASCADE_LAKE_CPUINFO = """
processor	: 0
vendor_id	: GenuineIntel
cpu family	: 6
model		: 85
model name	: Intel(R) Xeon(R) CPU @ 2.00GHz
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ss ht syscall nx pdpe1gb rdtscp lm constant_tsc rep_good nopl xtopology nonstop_tsc cpuid tsc_known_freq pni pclmulqdq ssse3 fma cx16 pcid sse4_1 sse4_2 x2apic movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm abm 3dnowprefetch invpcid_single ssbd ibrs ibpb stibp fsgsbase tsc_adjust bmi1 hle avx2 smep bmi2 erms invpcid rtm mpx avx512f avx512dq rdseed adx smap clflushopt clwb avx512cd avx512bw avx512vl xsaveopt xsavec xgetbv1 xsaves arat avx512_vnni md_clear arch_capabilities
"""

    INTEL_ICE_LAKE_CPUINFO = """
processor	: 0
vendor_id	: GenuineIntel
cpu family	: 6
model		: 106
model name	: Intel(R) Xeon(R) Platinum 8375C CPU @ 2.90GHz
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ss ht syscall nx pdpe1gb rdtscp lm constant_tsc arch_perfmon rep_good nopl xtopology nonstop_tsc cpuid tsc_known_freq pni pclmulqdq dtes64 monitor ds_cpl vmx smx est tm2 ssse3 sdbg fma cx16 xtpr pdcm pcid dca sse4_1 sse4_2 x2apic movbe popcnt tsc_deadline_timer aes xsave avx f16c rdrand lahf_lm abm 3dnowprefetch cpuid_fault epb cat_l3 invpcid_single intel_ppin ssbd mba ibrs ibpb stibp ibrs_enhanced tpr_shadow vnmi flexpriority ept vpid ept_ad fsgsbase tsc_adjust bmi1 avx2 smep bmi2 erms invpcid cqm rdt_a avx512f avx512dq rdseed adx smap avx512ifma clflushopt clwb intel_pt avx512cd sha_ni avx512bw avx512vl xsaveopt xsavec xgetbv1 xsaves cqm_llc cqm_occup_llc cqm_mbm_total cqm_mbm_local split_lock_detect wbnoinvd dtherm ida arat pln pts hwp hwp_act_window hwp_epp hwp_pkg_req avx512vbmi umip pku ospke avx512_vbmi2 gfni vaes vpclmulqdq avx512_vnni avx512_bitalg tme avx512_vpopcntdq la57 rdpid bus_lock_detect md_clear pconfig flush_l1d arch_capabilities
"""

    INTEL_SKYLAKE_CPUINFO = """
processor	: 0
vendor_id	: GenuineIntel
cpu family	: 6
model		: 85
model name	: Intel(R) Xeon(R) Platinum 8175M CPU @ 2.50GHz
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ss ht syscall nx pdpe1gb rdtscp lm constant_tsc rep_good nopl xtopology nonstop_tsc cpuid tsc_known_freq pni pclmulqdq ssse3 fma cx16 pcid sse4_1 sse4_2 x2apic movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm abm 3dnowprefetch invpcid_single ssbd ibrs ibpb stibp fsgsbase tsc_adjust bmi1 hle avx2 smep bmi2 erms invpcid rtm mpx avx512f avx512dq rdseed adx smap clflushopt clwb avx512cd avx512bw avx512vl xsaveopt xsavec xgetbv1 xsaves arat md_clear arch_capabilities
"""

    INTEL_HASWELL_CPUINFO = """
processor	: 0
vendor_id	: GenuineIntel
cpu family	: 6
model		: 63
model name	: Intel(R) Xeon(R) CPU E5-2670 v3 @ 2.30GHz
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ss ht syscall nx pdpe1gb rdtscp lm constant_tsc rep_good nopl xtopology nonstop_tsc cpuid tsc_known_freq pni pclmulqdq ssse3 fma cx16 pcid sse4_1 sse4_2 x2apic movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm abm invpcid_single ssbd ibrs ibpb stibp fsgsbase tsc_adjust bmi1 avx2 smep bmi2 erms invpcid xsaveopt xsavec xgetbv1 xsaves arat
"""

    # -------------------------------------------------------------------------
    # Tests for CpuModel.identify()
    # -------------------------------------------------------------------------

    def test_identify_amd_milan(self):
        """Test identification of AMD EPYC Milan (Zen 3)."""
        model = CpuModel.identify(self.AMD_MILAN_CPUINFO)
        self.assertEqual(model, CpuModel.AMD_MILAN)
        self.assertEqual(model.display_name, "AMD EPYC 3rd Gen (Milan / Zen 3)")

    def test_identify_amd_rome(self):
        """Test identification of AMD EPYC Rome (Zen 2)."""
        model = CpuModel.identify(self.AMD_ROME_CPUINFO)
        self.assertEqual(model, CpuModel.AMD_ROME)
        self.assertEqual(model.display_name, "AMD EPYC 2nd Gen (Rome / Zen 2)")

    def test_identify_amd_genoa(self):
        """Test identification of AMD EPYC Genoa (Zen 4)."""
        model = CpuModel.identify(self.AMD_GENOA_CPUINFO)
        self.assertEqual(model, CpuModel.AMD_GENOA)
        self.assertEqual(model.display_name, "AMD EPYC 4th Gen (Genoa / Zen 4)")

    def test_identify_intel_cascade_lake(self):
        """Test identification of Intel Xeon Cascade Lake."""
        model = CpuModel.identify(self.INTEL_CASCADE_LAKE_CPUINFO)
        self.assertEqual(model, CpuModel.INTEL_CASCADE_LAKE)
        self.assertEqual(model.display_name, "Intel Xeon 2nd Gen (Cascade Lake)")

    def test_identify_intel_ice_lake(self):
        """Test identification of Intel Xeon Ice Lake."""
        model = CpuModel.identify(self.INTEL_ICE_LAKE_CPUINFO)
        self.assertEqual(model, CpuModel.INTEL_ICE_LAKE)
        self.assertEqual(model.display_name, "Intel Xeon 3rd Gen (Ice Lake)")

    def test_identify_intel_skylake(self):
        """Test identification of Intel Xeon Skylake."""
        model = CpuModel.identify(self.INTEL_SKYLAKE_CPUINFO)
        self.assertEqual(model, CpuModel.INTEL_SKYLAKE)
        self.assertEqual(model.display_name, "Intel Xeon 1st Gen (Skylake)")

    def test_identify_intel_haswell(self):
        """Test identification of Intel Xeon Haswell."""
        model = CpuModel.identify(self.INTEL_HASWELL_CPUINFO)
        self.assertEqual(model, CpuModel.INTEL_HASWELL)
        self.assertEqual(model.display_name, "Intel Xeon v3 (Haswell)")

    def test_identify_unknown_missing_vendor(self):
        """Test that missing vendor_id returns UNKNOWN."""
        cpuinfo = """
processor	: 0
flags		: fpu vme de pse tsc
"""
        model = CpuModel.identify(cpuinfo)
        self.assertEqual(model, CpuModel.UNKNOWN)

    def test_identify_unknown_missing_flags(self):
        """Test that missing flags returns UNKNOWN."""
        cpuinfo = """
processor	: 0
vendor_id	: GenuineIntel
"""
        model = CpuModel.identify(cpuinfo)
        self.assertEqual(model, CpuModel.UNKNOWN)

    def test_identify_unknown_vendor(self):
        """Test that unknown vendor returns UNKNOWN."""
        cpuinfo = """
processor	: 0
vendor_id	: UnknownCPU
flags		: fpu vme de pse tsc
"""
        model = CpuModel.identify(cpuinfo)
        self.assertEqual(model, CpuModel.UNKNOWN)

    def test_identify_empty_input(self):
        """Test that empty input returns UNKNOWN."""
        model = CpuModel.identify("")
        self.assertEqual(model, CpuModel.UNKNOWN)

    # -------------------------------------------------------------------------
    # Tests for backward compatibility function
    # -------------------------------------------------------------------------

    def test_identify_cpu_model_function_returns_string(self):
        """Test that identify_cpu_model() returns string (backward compat)."""
        result = identify_cpu_model(self.AMD_MILAN_CPUINFO)
        self.assertIsInstance(result, str)
        self.assertEqual(result, "AMD EPYC 3rd Gen (Milan / Zen 3)")

    def test_identify_cpu_model_function_matches_enum(self):
        """Test that function result matches enum display_name."""
        for cpuinfo, expected_enum in [
            (self.AMD_MILAN_CPUINFO, CpuModel.AMD_MILAN),
            (self.AMD_ROME_CPUINFO, CpuModel.AMD_ROME),
            (self.INTEL_CASCADE_LAKE_CPUINFO, CpuModel.INTEL_CASCADE_LAKE),
            (self.INTEL_ICE_LAKE_CPUINFO, CpuModel.INTEL_ICE_LAKE),
        ]:
            with self.subTest(expected=expected_enum):
                func_result = identify_cpu_model(cpuinfo)
                enum_result = CpuModel.identify(cpuinfo)
                self.assertEqual(func_result, enum_result.display_name)

    # -------------------------------------------------------------------------
    # Tests for enum properties
    # -------------------------------------------------------------------------

    def test_enum_str_returns_display_name(self):
        """Test that str(CpuModel.X) returns the display_name."""
        self.assertEqual(str(CpuModel.AMD_MILAN), "AMD EPYC 3rd Gen (Milan / Zen 3)")
        self.assertEqual(str(CpuModel.INTEL_CASCADE_LAKE), "Intel Xeon 2nd Gen (Cascade Lake)")

    def test_enum_display_names_are_unique(self):
        """Test that all enum display names are unique."""
        display_names = [m.display_name for m in CpuModel]
        self.assertEqual(len(display_names), len(set(display_names)))

    def test_enum_iteration(self):
        """Test that we can iterate over all enum members."""
        members = list(CpuModel)
        self.assertGreater(len(members), 10)  # We have at least 10+ CPU models
        self.assertIn(CpuModel.AMD_MILAN, members)
        self.assertIn(CpuModel.INTEL_CASCADE_LAKE, members)
        self.assertIn(CpuModel.UNKNOWN, members)

    def test_enum_comparison(self):
        """Test that enum members can be compared."""
        model1 = CpuModel.identify(self.AMD_MILAN_CPUINFO)
        model2 = CpuModel.AMD_MILAN
        self.assertEqual(model1, model2)
        self.assertIs(model1, model2)

    def test_all_intel_models_have_intel_in_display_name(self):
        """Test that all Intel enum members have 'Intel' in their display_name."""
        intel_models = [m for m in CpuModel if m.name.startswith('INTEL_')]
        for model in intel_models:
            self.assertIn('Intel', model.display_name)

    def test_all_amd_models_have_amd_in_display_name(self):
        """Test that all AMD enum members have 'AMD' in their display_name."""
        amd_models = [m for m in CpuModel if m.name.startswith('AMD_')]
        for model in amd_models:
            self.assertIn('AMD', model.display_name)


class TestCpuModelSignature(unittest.TestCase):
    """Tests for CpuModel signature and pinning methods."""

    def test_get_signature_returns_tuple_for_pinnable_models(self):
        """Test that pinnable models return (vendor, flags, excluded_flags) tuple."""
        signature = CpuModel.AMD_MILAN.get_signature()
        self.assertIsNotNone(signature)
        vendor, flags, excluded_flags = signature
        self.assertEqual(vendor, "AuthenticAMD")
        self.assertIsInstance(flags, list)
        self.assertIn("vaes", flags)
        self.assertIn("vpclmulqdq", flags)
        self.assertIn("fsrm", flags)
        # Milan should exclude AVX-512 flags (which Genoa has)
        self.assertIsInstance(excluded_flags, list)
        self.assertIn("avx512f", excluded_flags)

    def test_get_signature_intel_cascade_lake(self):
        """Test Intel Cascade Lake signature."""
        signature = CpuModel.INTEL_CASCADE_LAKE.get_signature()
        self.assertIsNotNone(signature)
        vendor, flags, excluded_flags = signature
        self.assertEqual(vendor, "GenuineIntel")
        self.assertIn("avx512_vnni", flags)
        self.assertIsInstance(excluded_flags, list)

    def test_get_signature_returns_none_for_unknown(self):
        """Test that UNKNOWN model returns None."""
        signature = CpuModel.UNKNOWN.get_signature()
        self.assertIsNone(signature)

    def test_get_signature_returns_none_for_legacy_models(self):
        """Test that legacy models return None."""
        self.assertIsNone(CpuModel.INTEL_LEGACY.get_signature())
        self.assertIsNone(CpuModel.AMD_LEGACY.get_signature())

    def test_can_be_pinned_true_for_specific_models(self):
        """Test that specific models can be pinned."""
        self.assertTrue(CpuModel.AMD_MILAN.can_be_pinned())
        self.assertTrue(CpuModel.AMD_ROME.can_be_pinned())
        self.assertTrue(CpuModel.AMD_GENOA.can_be_pinned())
        self.assertTrue(CpuModel.INTEL_CASCADE_LAKE.can_be_pinned())
        self.assertTrue(CpuModel.INTEL_ICE_LAKE.can_be_pinned())
        self.assertTrue(CpuModel.INTEL_SKYLAKE.can_be_pinned())

    def test_can_be_pinned_false_for_legacy_and_unknown(self):
        """Test that legacy and unknown models cannot be pinned."""
        self.assertFalse(CpuModel.UNKNOWN.can_be_pinned())
        self.assertFalse(CpuModel.INTEL_LEGACY.can_be_pinned())
        self.assertFalse(CpuModel.AMD_LEGACY.can_be_pinned())

    def test_all_pinnable_models_have_valid_signatures(self):
        """Test that all pinnable models have valid signatures."""
        for model in CpuModel:
            if model.can_be_pinned():
                signature = model.get_signature()
                self.assertIsNotNone(signature, f"{model.name} should have a signature")
                vendor, flags, excluded_flags = signature
                self.assertIn(vendor, ["GenuineIntel", "AuthenticAMD"], 
                             f"{model.name} has unexpected vendor: {vendor}")
                self.assertIsInstance(flags, list)
                self.assertGreater(len(flags), 0, f"{model.name} should have at least one flag")
                self.assertIsInstance(excluded_flags, list)

    def test_signature_flags_match_identification_logic(self):
        """Test that signature flags are sufficient for identification."""
        # For each pinnable model, verify that cpuinfo with those flags identifies correctly
        for model in CpuModel:
            if not model.can_be_pinned():
                continue
            
            vendor, flags, excluded_flags = model.get_signature()
            # Build a minimal cpuinfo with just vendor and flags (no excluded flags)
            cpuinfo = f"vendor_id\t: {vendor}\nflags\t\t: {' '.join(flags)}"
            
            identified = CpuModel.identify(cpuinfo)
            self.assertEqual(identified, model, 
                f"Model {model.name} with flags {flags} identified as {identified.name}")

    def test_excluded_flags_prevent_misidentification(self):
        """Test that excluded flags correctly distinguish between generations."""
        # Genoa cpuinfo should NOT match Milan because Milan excludes avx512f
        genoa_cpuinfo = "vendor_id\t: AuthenticAMD\nflags\t\t: vaes vpclmulqdq fsrm avx512f avx512dq avx512vl"
        model = CpuModel.identify(genoa_cpuinfo)
        self.assertEqual(model, CpuModel.AMD_GENOA)
        self.assertNotEqual(model, CpuModel.AMD_MILAN)
        
        # Milan cpuinfo should match Milan (no avx512f)
        milan_cpuinfo = "vendor_id\t: AuthenticAMD\nflags\t\t: vaes vpclmulqdq fsrm clzero"
        model = CpuModel.identify(milan_cpuinfo)
        self.assertEqual(model, CpuModel.AMD_MILAN)

    def test_milan_excluded_flags_property(self):
        """Test that Milan's excluded_flags property returns correct values."""
        excluded = CpuModel.AMD_MILAN.excluded_flags
        self.assertIn("avx512f", excluded)


class TestCpuModelRealWorldData(unittest.TestCase):
    """Tests using real-world cpuinfo data from benchmark runs."""

    def test_real_world_cpuinfo_samples(self):
        """Test with a variety of real-world cpuinfo samples."""
        # These are simplified versions that should still be identifiable
        # Note: Milan must NOT have avx512f (it's in excluded_flags)
        test_cases = [
            # (cpuinfo_snippet, expected_model_or_list)
            (
                # Milan: has vaes/vpclmulqdq/fsrm but NOT avx512f
                "vendor_id\t: AuthenticAMD\nflags\t\t: vaes vpclmulqdq fsrm clzero avx2",
                CpuModel.AMD_MILAN
            ),
            (
                # Rome: has clzero/rdpid/clwb/wbnoinvd but NOT vaes
                "vendor_id\t: AuthenticAMD\nflags\t\t: clzero rdpid clwb wbnoinvd avx2",
                CpuModel.AMD_ROME
            ),
            (
                # Genoa: has avx512f/avx512dq/avx512vl (also has vaes/vpclmulqdq/fsrm but avx512f wins)
                "vendor_id\t: AuthenticAMD\nflags\t\t: avx512f avx512dq avx512vl avx2 vaes vpclmulqdq fsrm",
                CpuModel.AMD_GENOA
            ),
            (
                # Cascade Lake: has avx512_vnni but NOT avx512_bf16 or gfni
                "vendor_id\t: GenuineIntel\nflags\t\t: avx512f avx512dq avx512cd avx512bw avx512vl avx512_vnni",
                CpuModel.INTEL_CASCADE_LAKE
            ),
            (
                # Ice Lake: has avx512_vnni + vaes + vpclmulqdq + gfni but NOT amx_bf16
                "vendor_id\t: GenuineIntel\nflags\t\t: avx512f avx512dq avx512cd avx512bw avx512vl avx512_vnni vaes vpclmulqdq gfni",
                CpuModel.INTEL_ICE_LAKE
            ),
        ]

        for cpuinfo, expected in test_cases:
            with self.subTest(expected=expected):
                model = CpuModel.identify(cpuinfo)
                self.assertEqual(model, expected)


if __name__ == '__main__':
    unittest.main()
