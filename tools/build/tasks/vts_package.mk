#
# Copyright (C) 2017 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Build rules for VTS (Vendor Test Suite) that includes VTF and tests.

LOCAL_PATH := $(call my-dir)

#include $(LOCAL_PATH)/vtf_package.mk

build_utils_dir := $(LOCAL_PATH)/../utils

include $(LOCAL_PATH)/list/vts_adapter_package_list.mk
include $(LOCAL_PATH)/list/vts_spec_file_list.mk
include $(LOCAL_PATH)/list/vts_test_bin_package_list.mk
include $(LOCAL_PATH)/list/vts_test_lib_package_list.mk
include $(LOCAL_PATH)/list/vts_test_lib_hal_package_list.mk
include $(LOCAL_PATH)/list/vts_test_lib_hidl_package_list.mk
include $(LOCAL_PATH)/list/vts_func_fuzzer_package_list.mk
include $(LOCAL_PATH)/list/vts_test_host_lib_package_list.mk
include $(LOCAL_PATH)/list/vts_test_host_bin_package_list.mk
include $(LOCAL_PATH)/list/vts_test_hidl_hal_hash_list.mk
include $(LOCAL_PATH)/list/vts_vndk_abi_dump_package_list.mk
include $(build_utils_dir)/vts_package_utils.mk
-include external/linux-kselftest/android/kselftest_test_list.mk
-include external/ltp/android/ltp_package_list.mk

VTS_OUT_ROOT := $(HOST_OUT)/vts
VTS_TESTCASES_OUT := $(VTS_OUT_ROOT)/android-vts/testcases

# Packaging rule for android-vts.zip
test_suite_name := vts
test_suite_tradefed := vts-tradefed
test_suite_readme := test/vts/README.md

include $(BUILD_SYSTEM)/tasks/tools/compatibility.mk

.PHONY: vts
vts: $(compatibility_zip) vtslab adb
$(call dist-for-goals, vts, $(compatibility_zip))

# Packaging rule for android-vts.zip's testcases dir (DATA subdir).
target_native_modules := \
    $(kselftest_modules) \
    ltp \
    $(ltp_packages) \
    $(vts_adapter_package_list) \
    $(vts_test_bin_packages) \
    $(vts_test_lib_hal_packages) \
    $(vts_test_lib_hidl_packages) \
    $(vts_func_fuzzer_packages) \

target_native_copy_pairs := \
  $(call target-native-copy-pairs,$(target_native_modules),$(VTS_TESTCASES_OUT))

# Packaging rule for android-vts.zip's testcases dir (spec subdir).

target_spec_modules := \
  $(VTS_SPEC_FILE_LIST)

target_spec_copy_pairs :=
$(foreach m,$(target_spec_modules),\
  $(eval my_spec_copy_dir :=\
    spec/$(word 2,$(subst android/frameworks/, frameworks/hardware/interfaces/,\
                    $(subst android/hardware/, hardware/interfaces/,\
                      $(subst android/hidl/, system/libhidl/transport/,\
                        $(subst android/system/, system/hardware/interfaces/,$(dir $(m)))))))/vts)\
  $(eval my_spec_copy_file := $(notdir $(m)))\
  $(eval my_spec_copy_dest := $(my_spec_copy_dir)/$(my_spec_copy_file))\
  $(eval target_spec_copy_pairs += $(m):$(VTS_TESTCASES_OUT)/$(my_spec_copy_dest)))

$(foreach m,$(vts_spec_file_list),\
  $(if $(wildcard $(m)),\
    $(eval target_spec_copy_pairs += $(m):$(VTS_TESTCASES_OUT)/spec/$(m))))

target_trace_files := \
  $(call find-files-in-subdirs,test/vts-testcase/hal-trace,"*.vts.trace" -and -type f,.) \

target_trace_copy_pairs := \
$(foreach f,$(target_trace_files),\
    test/vts-testcase/hal-trace/$(f):$(VTS_TESTCASES_OUT)/hal-hidl-trace/test/vts-testcase/hal-trace/$(f))

target_hal_hash_modules := \
    $(vts_test_hidl_hal_hash_list) \

target_hal_hash_copy_pairs :=
$(foreach m,$(target_hal_hash_modules),\
  $(if $(wildcard $(m)),\
    $(eval target_hal_hash_copy_pairs += $(m):$(VTS_TESTCASES_OUT)/hal-hidl-hash/$(m))))

host_vndk_abi_dumps := \
  $(foreach target,$(vts_vndk_abi_dump_target_tuple_list),\
    $(call create-vndk-abi-dump-from-target,$(target),$(VTS_TESTCASES_OUT)/vts/testcases/vndk/golden))

media_test_res_files := \
  $(call find-files-in-subdirs,hardware/interfaces/media/res,"*.*" -and -type f,.) \

media_test_res_copy_pairs := \
  $(foreach f,$(media_test_res_files),\
    hardware/interfaces/media/res/$(f):$(VTS_TESTCASES_OUT)/DATA/media/res/$(f))

nbu_p2p_apk_files := \
  $(call find-files-in-subdirs,test/vts-testcase/nbu/src,"*.apk" -and -type f,.)

nbu_p2p_apk_copy_pairs := \
  $(foreach f,$(nbu_p2p_apk_files),\
      test/vts-testcase/nbu/src/$(f):$(VTS_TESTCASES_OUT)/DATA/app/nbu/$(f))

performance_test_res_files := \
  $(call find-files-in-subdirs,test/vts-testcase/performance/res/,"*.*" -and -type f,.) \

performance_test_res_copy_pairs := \
  $(foreach f,$(performance_test_res_files),\
    test/vts-testcase/performance/res/$(f):$(VTS_TESTCASES_OUT)/DATA/performance/res/$(f))

audio_test_res_files := \
  $(call find-files-in-subdirs,hardware/interfaces/audio,"*.xsd" -and -type f,.) \

audio_test_res_copy_pairs := \
  $(foreach f,$(audio_test_res_files),\
    hardware/interfaces/audio/$(f):$(VTS_TESTCASES_OUT)/DATA/hardware/interfaces/audio/$(f))

ifeq (REL,$(PLATFORM_VERSION_CODENAME))
LATEST_VNDK_LIB_EXTRA_LIST := development/vndk/tools/definition-tool/datasets/vndk-lib-extra-list-$(PLATFORM_VNDK_VERSION).txt
else
LATEST_VNDK_LIB_EXTRA_LIST := development/vndk/tools/definition-tool/datasets/vndk-lib-extra-list-current.txt
endif

vndk_test_res_copy_pairs := \
  $(LATEST_VNDK_LIB_LIST):$(VTS_TESTCASES_OUT)/vts/testcases/vndk/golden/$(PLATFORM_VNDK_VERSION)/vndk-lib-list.txt \
  $(LATEST_VNDK_LIB_EXTRA_LIST):$(VTS_TESTCASES_OUT)/vts/testcases/vndk/golden/$(PLATFORM_VNDK_VERSION)/vndk-lib-extra-list.txt \

kernel_rootdir_test_rc_files := \
  $(call find-files-in-subdirs,system/core/rootdir,"*.rc" -and -type f,.) \

kernel_rootdir_test_rc_copy_pairs := \
  $(foreach f,$(kernel_rootdir_test_rc_files),\
    system/core/rootdir/$(f):$(VTS_TESTCASES_OUT)/vts/testcases/kernel/api/rootdir/init_rc_files/$(f)) \

acts_testcases_files := \
  $(call find-files-in-subdirs,tools/test/connectivity/acts/tests/google,"*.py" -and -type f,.)

acts_testcases_copy_pairs := \
  $(foreach f,$(acts_testcases_files),\
    tools/test/connectivity/acts/tests/google/$(f):$(VTS_TESTCASES_OUT)/vts/testcases/acts/$(f))

system_property_compatibility_test_res_copy_pairs := \
  system/sepolicy/public/property_contexts:$(VTS_TESTCASES_OUT)/vts/testcases/security/system_property/data/property_contexts

# For VtsSecurityAvb
gsi_key_copy_pairs := \
  system/core/rootdir/avb/q-gsi.avbpubkey:$(VTS_TESTCASES_OUT)/DATA/avb/q-gsi.avbpubkey

$(VTS_TESTCASES_OUT)/vts/testcases/vndk/golden/platform_vndk_version.txt:
	@echo -n $(PLATFORM_VNDK_VERSION) > $@

# Package roots that contains /prebuilt_hashes, and thus can be analyzed.
vts_hidl_hals_package_roots := \
    android.hardware:hardware/interfaces \

vts_hidl_hals := \
    $(call find-files-in-subdirs, ., "*.hal" -and -type f, \
        $(foreach pair,$(vts_hidl_hals_package_roots),$(call word-colon,2,$(pair))))

vts_hidl_hashes := \
    $(foreach pair,$(vts_hidl_hals_package_roots),$(call word-colon,2,$(pair))/current.txt) \
    $(call find-files-in-subdirs, ., "*.txt" -and -type f, \
        $(foreach pair,$(vts_hidl_hals_package_roots),$(call word-colon,2,$(pair))/prebuilt_hashes))

vts_hidl_hals_dump := $(VTS_TESTCASES_OUT)/DATA/etc/hidl_hals_for_release.json
$(vts_hidl_hals_dump): $(HOST_OUT)/bin/dump_hals_for_release $(vts_hidl_hals) $(vts_hidl_hashes)
	$< --pretty --package-root $(vts_hidl_hals_package_roots) \
	    --filter-out '::types$$' '^android[.]hardware[.]tests[.]' \
	    -- $(vts_hidl_hashes) > $@

# for VTF (Vendor Test Framework) packages
VTF_OUT_ROOT := $(HOST_OUT)/vts
VTF_TESTCASES_OUT := $(VTF_OUT_ROOT)/android-vts/testcases
VTF_TOOLS_OUT := $(VTF_OUT_ROOT)/android-vts/tools
VTF_EXTRA_SCRIPTS :=

xsd_config_files := \
  system/libvintf/xsd/compatibilityMatrix/compatibility_matrix.xsd:$(VTS_TESTCASES_OUT)/DATA/etc/compatibility_matrix.xsd \
  system/libvintf/xsd/halManifest/hal_manifest.xsd:$(VTS_TESTCASES_OUT)/DATA/etc/hal_manifest.xsd \
  frameworks/av/media/libstagefright/xmlparser/media_codecs.xsd:$(VTS_TESTCASES_OUT)/DATA/etc/media_codecs.xsd \
  frameworks/av/media/libmedia/xsd/media_profiles.xsd:$(VTS_TESTCASES_OUT)/DATA/etc/media_profiles.xsd \
  frameworks/base/services/core/xsd/default-permissions.xsd:$(VTS_TESTCASES_OUT)/DATA/etc/default-permissions.xsd \
  frameworks/base/core/xsd/permission.xsd:$(VTS_TESTCASES_OUT)/DATA/etc/permission.xsd

include $(LOCAL_PATH)/framework/vtf_package.mk

# finally back to the rules for VTS (Vendor Test Suite) packages
vts_copy_pairs := \
  $(vtf_copy_pairs) \
  $(vts_test_core_copy_pairs) \
  $(call copy-many-files,$(target_native_copy_pairs)) \
  $(call copy-many-files,$(target_spec_copy_pairs)) \
  $(call copy-many-files,$(target_trace_copy_pairs)) \
  $(call copy-many-files,$(media_test_res_copy_pairs)) \
  $(call copy-many-files,$(nbu_p2p_apk_copy_pairs)) \
  $(call copy-many-files,$(performance_test_res_copy_pairs)) \
  $(call copy-many-files,$(audio_test_res_copy_pairs)) \
  $(call copy-many-files,$(vndk_test_res_copy_pairs)) \
  $(call copy-many-files,$(kernel_rootdir_test_rc_copy_pairs)) \
  $(call copy-many-files,$(acts_testcases_copy_pairs)) \
  $(call copy-many-files,$(system_property_compatibility_test_res_copy_pairs)) \
  $(call copy-many-files,$(xsd_config_files)) \
  $(call copy-many-files,$(gsi_key_copy_pairs)) \
  $(VTS_TESTCASES_OUT)/vts/testcases/vndk/golden/platform_vndk_version.txt \
  $(vts_hidl_hals_dump) \

$(compatibility_zip): $(vts_copy_pairs) $(host_vndk_abi_dumps)

-include vendor/google_vts/tools/build/vts_package_vendor.mk
