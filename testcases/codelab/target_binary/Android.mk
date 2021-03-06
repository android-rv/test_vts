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
LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := vts_codelab_target_binary
LOCAL_MODULE_TAGS := optional
LOCAL_SRC_FILES := vts_codelab_target_binary.c
LOCAL_SHARED_LIBRARIES := libutils libcutils liblog
LOCAL_C_INCLUDES += bionic
LOCAL_CFLAGS := -Werror -Wall
include $(BUILD_NATIVE_TEST)

include $(CLEAR_VARS)
LOCAL_MODULE := VtsCodelabTargetBinary
include test/vts/tools/build/Android.host_config.mk
