//
// Copyright 2018 The Android Open Source Project
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

#ifndef __VTS_RESOURCE_VTSRESOURCEMANAGER_H
#define __VTS_RESOURCE_VTSRESOURCEMANAGER_H

#include <android-base/logging.h>
#include <google/protobuf/repeated_field.h>
#include <google/protobuf/text_format.h>

#include "fmq_driver/VtsFmqDriver.h"
#include "hidl_memory_driver/VtsHidlMemoryDriver.h"
#include "test/vts/proto/ComponentSpecificationMessage.pb.h"
#include "test/vts/proto/VtsResourceControllerMessage.pb.h"

using namespace std;

namespace android {
namespace vts {

// A class that manages all resources allocated on the target side.
// Resources include fast message queue, hidl_memory, hidl_handle.
// This class only manages fast message queue now.
// TODO: Add hidl_memory and hidl_handle managers when they are implemented.
// Example:
//   // Initialize a manager.
//   VtsResourceManager manager;
//
//   // Generate some FMQ request (e.g. creating a queue.).
//   FmqRequestMessage fmq_request;
//   fmq_request.set_operation(FMQ_PROTO_CREATE);
//   fmq_request.set_data_type("uint16_t");
//   fmq_request.set_sync(true);
//   fmq_request.set_queue_size(2048);
//   fmq_request.set_blocking(false);
//
//   // receive response.
//   FmqRequestResponse fmq_response;
//   // This will ask FMQ driver to process request and send response.
//   ProcessFmqCommand(fmq_request, &fmq_response);
class VtsResourceManager {
 public:
  // Constructor to set up the resource manager.
  VtsResourceManager();

  // Destructor to clean up the resource manager.
  ~VtsResourceManager();

  // Processes command for operations on hidl_memory.
  //
  // @param hidl_memory_request  contains arguments for the operation.
  // @param hidl_memory_response to be filled by the function.
  void ProcessHidlMemoryCommand(
      const HidlMemoryRequestMessage& hidl_memory_request,
      HidlMemoryResponseMessage* hidl_memory_response);

  // Registers the memory object in hidl_memory_driver_ given the hidl_memory
  // pointer address provided in hidl_memory_msg.
  //
  // @param hidl_memory_msg stores hidl_memory pointer, used to find actual
  //                        memory pointer.
  //
  // @return mem_id assigned to the new memory object.
  int RegisterHidlMemory(const VariableSpecificationMessage& hidl_memory_msg);

  // Gets hidl_memory pointer address in hidl_memory_driver_.
  // If caller wants to use a memory object in the driver, it specifies mem_id
  // in MemoryDataValueMessage. This method calls hidl_memory_driver to locate
  // the memory object with mem_id, and stores the address in result pointer.
  //
  // @param hidl_memory_msg contains memory object mem_id.
  // @param result          stores hidl_memory pointer.
  //
  // @return true if the memory object with mem_id is found, and stores pointer
  //              address in result,
  //         false otherwise.
  bool GetHidlMemoryAddress(const VariableSpecificationMessage& hidl_memory_msg,
                            size_t* result);

  // Processes command for operations on Fast Message Queue.
  //
  // @param fmq_request  contains arguments for the operation.
  // @param fmq_response to be filled by the function.
  void ProcessFmqCommand(const FmqRequestMessage& fmq_request,
                         FmqResponseMessage* fmq_response);

  // Registers a fmq in fmq_driver_ given the information provided in
  // queue_msg.
  // This message stores queue data_type, sync option, and existing
  // descriptor address. This method recasts the address into a pointer
  // and passes it to fmq_driver_.
  //
  // @param queue_msg stores queue information, data_type, sync option,
  //                  and queue descriptor address.
  //
  // @return queue_id assigned to the new queue object.
  int RegisterFmq(const VariableSpecificationMessage& queue_msg);

  // Gets queue descriptor address specified in VariableSpecificationMessage.
  // The message contains type of data in the queue, queue flavor,
  // and queue id. The method calls fmq_driver to locate the address of the
  // descriptor using these information, then stores the address in
  // result pointer.
  //
  // @param queue_msg contains queue information.
  // @param result    to store queue descriptor pointer address.
  //
  // @return true if queue is found and type matches, and stores the descriptor
  //              address in result.
  //         false otherwise.
  bool GetQueueDescAddress(const VariableSpecificationMessage& queue_msg,
                           size_t* result);

 private:
  // Calls internal methods in fmq_driver to execute FMQ read/write operations.
  //
  // @param op             read/write operation.
  // @param data_type      type of data in the queue.
  // @param sync           whether the queue is synchronized (only has one
  //                       reader).
  // @param queue_id       identifies the message queue object.
  // @param data           write/read data.
  // @param data_size      length of data.
  // @param time_out_nanos wait time (in nanoseconds) when blocking.
  //
  // @return true if the operation succeeds, false otherwise.
  bool ProcessFmqReadWriteInternal(FmqOp op, const string& data_type, bool sync,
                                   int queue_id, void* data, size_t data_size,
                                   int64_t time_out_nanos);

  // Processes write operation on the FMQ.
  // The function determines the data type of the write operation,
  // and calls the corresponding methods to perform write.
  // The results are stored in fmq_response.
  //
  // @param fmq_request  arguments for the FMQ operation.
  // @param fmq_response to be filled by the function.
  void ProcessFmqWrite(const FmqRequestMessage& fmq_request,
                       FmqResponseMessage* fmq_response);

  // Processes read operation on the FMQ.
  // The function determines the data type of the read operation,
  // and calls the corresponding methods to perform read.
  // The results are stored in fmq_response.
  //
  // @param fmq_request  arguments for the FMQ operation.
  // @param fmq_response to be filled by the function.
  void ProcessFmqRead(const FmqRequestMessage& fmq_request,
                      FmqResponseMessage* fmq_response);

  // Manages Fast Message Queue (FMQ) driver.
  VtsFmqDriver fmq_driver_;
  // Manages hidl_memory driver.
  VtsHidlMemoryDriver hidl_memory_driver_;
};

}  // namespace vts
}  // namespace android
#endif  //__VTS_RESOURCE_VTSRESOURCEMANAGER_H
