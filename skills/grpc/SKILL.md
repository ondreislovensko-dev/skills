---
name: grpc
description: >-
  Build high-performance RPC services with gRPC and Protocol Buffers. Use when a
  user asks to create gRPC services, define protobuf schemas, implement streaming
  RPCs, build microservice communication, set up service-to-service calls, implement
  bidirectional streaming, add interceptors/middleware to gRPC, generate client stubs,
  handle gRPC errors, implement health checks, configure load balancing, or build
  gRPC-Web for browser clients. Covers unary, server/client/bidirectional streaming,
  interceptors, deadlines, metadata, reflection, and production patterns.
license: Apache-2.0
compatibility: "Node.js 18+, Python 3.9+, or Go 1.21+ (grpc, protobuf)"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: development
  tags: ["grpc", "rpc", "protobuf", "microservices", "streaming", "protocol-buffers"]
---

# gRPC

## Overview

Build high-performance, strongly-typed RPC services using gRPC and Protocol Buffers. gRPC uses HTTP/2 for transport, protobuf for serialization (10x smaller than JSON, 5-10x faster parsing), and generates client/server code in 12+ languages. Ideal for microservice communication, real-time streaming, and performance-critical APIs.

## Instructions

### Step 1: Install Tools

**Protocol Buffer Compiler:**
```bash
# macOS
brew install protobuf

# Ubuntu/Debian
apt install -y protobuf-compiler

# Verify
protoc --version
```

**Node.js:**
```bash
npm install @grpc/grpc-js @grpc/proto-loader
# Or with code generation:
npm install @grpc/grpc-js google-protobuf
npm install -D grpc-tools grpc_tools_node_protoc_ts
```

**Python:**
```bash
pip install grpcio grpcio-tools grpcio-reflection grpcio-health-checking
```

**Go:**
```bash
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
```

### Step 2: Define Protocol Buffers

```protobuf
// proto/user_service.proto
syntax = "proto3";

package userservice.v1;

option go_package = "github.com/myorg/myapp/gen/userservice/v1";

import "google/protobuf/timestamp.proto";
import "google/protobuf/empty.proto";
import "google/protobuf/field_mask.proto";

// Service definition
service UserService {
  // Unary RPCs
  rpc GetUser(GetUserRequest) returns (User);
  rpc CreateUser(CreateUserRequest) returns (User);
  rpc UpdateUser(UpdateUserRequest) returns (User);
  rpc DeleteUser(DeleteUserRequest) returns (google.protobuf.Empty);
  rpc ListUsers(ListUsersRequest) returns (ListUsersResponse);

  // Server streaming — server sends multiple responses
  rpc WatchUser(WatchUserRequest) returns (stream UserEvent);

  // Client streaming — client sends multiple requests
  rpc BatchCreateUsers(stream CreateUserRequest) returns (BatchCreateUsersResponse);

  // Bidirectional streaming
  rpc Chat(stream ChatMessage) returns (stream ChatMessage);
}

// Messages
message User {
  string id = 1;
  string email = 2;
  string name = 3;
  string avatar = 4;
  Role role = 5;
  google.protobuf.Timestamp created_at = 6;
  google.protobuf.Timestamp updated_at = 7;
}

enum Role {
  ROLE_UNSPECIFIED = 0;
  ROLE_USER = 1;
  ROLE_ADMIN = 2;
  ROLE_MODERATOR = 3;
}

message GetUserRequest {
  string id = 1;
}

message CreateUserRequest {
  string email = 1;
  string name = 2;
  string password = 3;
  Role role = 4;
}

message UpdateUserRequest {
  string id = 1;
  string name = 2;
  string avatar = 3;
  google.protobuf.FieldMask update_mask = 4;  // Which fields to update
}

message DeleteUserRequest {
  string id = 1;
}

message ListUsersRequest {
  int32 page_size = 1;       // Max items per page
  string page_token = 2;     // Cursor for next page
  string filter = 3;         // e.g., "role=ADMIN"
  string order_by = 4;       // e.g., "created_at desc"
}

message ListUsersResponse {
  repeated User users = 1;
  string next_page_token = 2;
  int32 total_count = 3;
}

message WatchUserRequest {
  string id = 1;
}

message UserEvent {
  enum EventType {
    EVENT_TYPE_UNSPECIFIED = 0;
    EVENT_TYPE_UPDATED = 1;
    EVENT_TYPE_DELETED = 2;
  }
  EventType type = 1;
  User user = 2;
  google.protobuf.Timestamp timestamp = 3;
}

message BatchCreateUsersResponse {
  int32 created_count = 1;
  repeated string failed_emails = 2;
}

message ChatMessage {
  string sender_id = 1;
  string text = 2;
  google.protobuf.Timestamp timestamp = 3;
}
```

Protobuf design rules:
- **Field numbers are forever** — never reuse or change them after deployment
- **Use `UNSPECIFIED = 0`** for enums — protobuf defaults to 0
- **`repeated` for lists** — not a separate List message
- **`google.protobuf.FieldMask`** for partial updates
- **`google.protobuf.Timestamp`** for dates (not int64 or string)
- **Package with version** — `userservice.v1` enables API versioning

### Step 3: Generate Code

**Python:**
```bash
python -m grpc_tools.protoc \
  -I proto \
  --python_out=gen \
  --grpc_python_out=gen \
  --pyi_out=gen \
  proto/user_service.proto
```

**Go:**
```bash
protoc -I proto \
  --go_out=gen --go_opt=paths=source_relative \
  --go-grpc_out=gen --go-grpc_opt=paths=source_relative \
  proto/user_service.proto
```

**Node.js (dynamic loading — no codegen needed):**
```javascript
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

const packageDef = protoLoader.loadSync('proto/user_service.proto', {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});
const proto = grpc.loadPackageDefinition(packageDef);
```

### Step 4: Server Implementation (Node.js)

```javascript
// src/server.js
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

const packageDef = protoLoader.loadSync('proto/user_service.proto', {
  keepCase: true, longs: String, enums: String, defaults: true, oneofs: true,
});
const proto = grpc.loadPackageDefinition(packageDef).userservice.v1;

const users = new Map();  // Replace with DB

const userService = {
  // Unary
  GetUser(call, callback) {
    const user = users.get(call.request.id);
    if (!user) {
      return callback({
        code: grpc.status.NOT_FOUND,
        message: `User ${call.request.id} not found`,
      });
    }
    callback(null, user);
  },

  CreateUser(call, callback) {
    const { email, name, password, role } = call.request;
    const id = crypto.randomUUID();
    const user = { id, email, name, role: role || 'ROLE_USER', created_at: { seconds: Date.now() / 1000 } };
    users.set(id, user);
    callback(null, user);
  },

  // Server streaming
  WatchUser(call) {
    const userId = call.request.id;
    const interval = setInterval(() => {
      const user = users.get(userId);
      if (user) {
        call.write({ type: 'EVENT_TYPE_UPDATED', user, timestamp: { seconds: Date.now() / 1000 } });
      }
    }, 5000);

    call.on('cancelled', () => clearInterval(interval));
  },

  // Client streaming
  BatchCreateUsers(call, callback) {
    let created = 0;
    const failed = [];

    call.on('data', (req) => {
      try {
        const id = crypto.randomUUID();
        users.set(id, { id, email: req.email, name: req.name, role: req.role || 'ROLE_USER' });
        created++;
      } catch {
        failed.push(req.email);
      }
    });

    call.on('end', () => {
      callback(null, { created_count: created, failed_emails: failed });
    });
  },

  // Bidirectional streaming
  Chat(call) {
    call.on('data', (message) => {
      // Echo back or broadcast to other streams
      call.write({
        sender_id: 'server',
        text: `Received: ${message.text}`,
        timestamp: { seconds: Date.now() / 1000 },
      });
    });

    call.on('end', () => call.end());
  },

  ListUsers(call, callback) {
    const { page_size = 20, page_token, filter } = call.request;
    const allUsers = Array.from(users.values());
    const startIndex = page_token ? parseInt(Buffer.from(page_token, 'base64').toString()) : 0;
    const pageUsers = allUsers.slice(startIndex, startIndex + page_size);
    const nextToken = startIndex + page_size < allUsers.length
      ? Buffer.from(String(startIndex + page_size)).toString('base64')
      : '';

    callback(null, {
      users: pageUsers,
      next_page_token: nextToken,
      total_count: allUsers.length,
    });
  },
};

const server = new grpc.Server();
server.addService(proto.UserService.service, userService);

server.bindAsync('0.0.0.0:50051', grpc.ServerCredentials.createInsecure(), (err, port) => {
  if (err) throw err;
  console.log(`gRPC server running on port ${port}`);
});
```

### Step 5: Server Implementation (Python)

```python
# server.py
import grpc
from concurrent import futures
from gen import user_service_pb2, user_service_pb2_grpc
from grpc_reflection.v1alpha import reflection
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
import uuid
import time

class UserService(user_service_pb2_grpc.UserServiceServicer):
    def __init__(self):
        self.users = {}

    def GetUser(self, request, context):
        user = self.users.get(request.id)
        if not user:
            context.abort(grpc.StatusCode.NOT_FOUND, f"User {request.id} not found")
        return user

    def CreateUser(self, request, context):
        user_id = str(uuid.uuid4())
        user = user_service_pb2.User(
            id=user_id,
            email=request.email,
            name=request.name,
            role=request.role or user_service_pb2.ROLE_USER,
        )
        user.created_at.GetCurrentTime()
        self.users[user_id] = user
        return user

    def WatchUser(self, request, context):
        """Server streaming — push updates."""
        while context.is_active():
            user = self.users.get(request.id)
            if user:
                yield user_service_pb2.UserEvent(
                    type=user_service_pb2.UserEvent.EVENT_TYPE_UPDATED,
                    user=user,
                )
            time.sleep(5)

    def BatchCreateUsers(self, request_iterator, context):
        """Client streaming — receive batch."""
        created = 0
        failed = []
        for req in request_iterator:
            try:
                user_id = str(uuid.uuid4())
                user = user_service_pb2.User(id=user_id, email=req.email, name=req.name)
                self.users[user_id] = user
                created += 1
            except Exception:
                failed.append(req.email)
        return user_service_pb2.BatchCreateUsersResponse(created_count=created, failed_emails=failed)

    def Chat(self, request_iterator, context):
        """Bidirectional streaming."""
        for message in request_iterator:
            yield user_service_pb2.ChatMessage(
                sender_id="server",
                text=f"Echo: {message.text}",
            )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    user_service_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)

    # Health checking
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("userservice.v1.UserService", health_pb2.HealthCheckResponse.SERVING)

    # Reflection (for grpcurl/grpcui)
    reflection.enable_server_reflection([
        user_service_pb2.DESCRIPTOR.services_by_name["UserService"].full_name,
        reflection.SERVICE_NAME,
    ], server)

    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC server running on port 50051")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
```

### Step 6: Client Implementation

**Node.js:**
```javascript
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

const packageDef = protoLoader.loadSync('proto/user_service.proto', {
  keepCase: true, longs: String, enums: String, defaults: true, oneofs: true,
});
const proto = grpc.loadPackageDefinition(packageDef).userservice.v1;

const client = new proto.UserService('localhost:50051', grpc.credentials.createInsecure());

// Unary call
client.GetUser({ id: '123' }, (err, user) => {
  if (err) return console.error(err.message);
  console.log('User:', user);
});

// With deadline
const deadline = new Date();
deadline.setSeconds(deadline.getSeconds() + 5);
client.GetUser({ id: '123' }, { deadline }, (err, user) => { /* ... */ });

// Server streaming
const stream = client.WatchUser({ id: '123' });
stream.on('data', (event) => console.log('Event:', event));
stream.on('error', (err) => console.error(err));
stream.on('end', () => console.log('Stream ended'));

// Client streaming
const batchStream = client.BatchCreateUsers((err, response) => {
  console.log(`Created: ${response.created_count}`);
});
batchStream.write({ email: 'a@test.com', name: 'Alice' });
batchStream.write({ email: 'b@test.com', name: 'Bob' });
batchStream.end();

// Bidirectional streaming
const chat = client.Chat();
chat.on('data', (msg) => console.log(`Server: ${msg.text}`));
chat.write({ sender_id: 'user1', text: 'Hello' });
chat.write({ sender_id: 'user1', text: 'How are you?' });
chat.end();
```

**Python:**
```python
import grpc
from gen import user_service_pb2, user_service_pb2_grpc

channel = grpc.insecure_channel("localhost:50051")
stub = user_service_pb2_grpc.UserServiceStub(channel)

# Unary
user = stub.GetUser(user_service_pb2.GetUserRequest(id="123"))

# With deadline
user = stub.GetUser(user_service_pb2.GetUserRequest(id="123"), timeout=5)

# Server streaming
for event in stub.WatchUser(user_service_pb2.WatchUserRequest(id="123")):
    print(f"Event: {event.type}")

# Client streaming
def generate_users():
    for name in ["Alice", "Bob", "Charlie"]:
        yield user_service_pb2.CreateUserRequest(email=f"{name.lower()}@test.com", name=name)

response = stub.BatchCreateUsers(generate_users())
print(f"Created: {response.created_count}")
```

### Step 7: Interceptors (Middleware)

```javascript
// Server interceptor — logging + auth
function loggingInterceptor(methodDescriptor, call) {
  const start = Date.now();
  const listener = new grpc.ServerListenerBuilder()
    .withOnReceiveMessage((message, next) => {
      console.log(`[${methodDescriptor.path}] Request received`);
      next(message);
    })
    .build();

  const responder = new grpc.ResponderBuilder()
    .withSendMessage((message, next) => {
      console.log(`[${methodDescriptor.path}] Response in ${Date.now() - start}ms`);
      next(message);
    })
    .withSendStatus((status, next) => {
      console.log(`[${methodDescriptor.path}] Status: ${status.code}`);
      next(status);
    })
    .build();

  return new grpc.ServerInterceptingCall(call, listener, responder);
}

// Auth interceptor
function authInterceptor(methodDescriptor, call) {
  const metadata = call.metadata;
  const token = metadata.get('authorization')[0];
  if (!token || !verifyToken(token)) {
    call.sendStatus({ code: grpc.status.UNAUTHENTICATED, details: 'Invalid token' });
    return new grpc.ServerInterceptingCall(call);
  }
  return new grpc.ServerInterceptingCall(call);
}

const server = new grpc.Server({ interceptors: [loggingInterceptor, authInterceptor] });
```

**Python interceptor:**
```python
class AuthInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)
        token = metadata.get("authorization")

        if not token or not verify_token(token):
            def abort(request, context):
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid token")
            return grpc.unary_unary_rpc_method_handler(abort)

        return continuation(handler_call_details)

server = grpc.server(
    futures.ThreadPoolExecutor(max_workers=10),
    interceptors=[AuthInterceptor()],
)
```

### Step 8: Error Handling

gRPC uses status codes (different from HTTP):
```
OK                  = 0    — Success
CANCELLED           = 1    — Client cancelled
UNKNOWN             = 2    — Unknown error
INVALID_ARGUMENT    = 3    — Bad input (like HTTP 400)
NOT_FOUND           = 5    — Resource not found (like HTTP 404)
ALREADY_EXISTS      = 6    — Duplicate (like HTTP 409)
PERMISSION_DENIED   = 7    — Forbidden (like HTTP 403)
UNAUTHENTICATED     = 16   — Not authenticated (like HTTP 401)
RESOURCE_EXHAUSTED  = 8    — Rate limited (like HTTP 429)
FAILED_PRECONDITION = 9    — State conflict
UNIMPLEMENTED       = 12   — Method not implemented
INTERNAL            = 13   — Server error (like HTTP 500)
UNAVAILABLE         = 14   — Service down (like HTTP 503)
DEADLINE_EXCEEDED   = 4    — Timeout
```

Rich error details:
```python
from google.rpc import error_details_pb2, status_pb2
from grpc_status import rpc_status

def CreateUser(self, request, context):
    if not request.email:
        detail = error_details_pb2.BadRequest()
        violation = detail.field_violations.add()
        violation.field = "email"
        violation.description = "Email is required"

        status = status_pb2.Status(
            code=grpc.StatusCode.INVALID_ARGUMENT.value[0],
            message="Validation failed",
        )
        status.details.add().Pack(detail)
        context.abort_with_status(rpc_status.to_status(status))
```

### Step 9: gRPC-Web (Browser Clients)

Browsers can't use HTTP/2 gRPC directly. Use a proxy:

```bash
# Envoy proxy (recommended)
# Or grpc-web with a Node proxy:
npm install @improbable-eng/grpc-web
```

```javascript
// Browser client
import { grpc } from '@improbable-eng/grpc-web';
import { UserService } from './gen/user_service_pb_service';
import { GetUserRequest } from './gen/user_service_pb';

const req = new GetUserRequest();
req.setId('123');

grpc.unary(UserService.GetUser, {
  request: req,
  host: 'https://api.example.com',
  onEnd: (response) => {
    if (response.status === grpc.Code.OK) {
      console.log(response.message.toObject());
    }
  },
});
```

### Step 10: Testing

```bash
# Install grpcurl (CLI tool for gRPC)
brew install grpcurl  # macOS
# or go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest

# List services (requires reflection enabled)
grpcurl -plaintext localhost:50051 list

# Describe service
grpcurl -plaintext localhost:50051 describe userservice.v1.UserService

# Call method
grpcurl -plaintext -d '{"email": "alice@test.com", "name": "Alice"}' \
  localhost:50051 userservice.v1.UserService/CreateUser

# Server streaming
grpcurl -plaintext -d '{"id": "123"}' \
  localhost:50051 userservice.v1.UserService/WatchUser
```

## Best Practices

1. **Proto design is your API contract** — review it as carefully as database schemas
2. **Never change field numbers** — add new fields, deprecate old ones with `reserved`
3. **Use `FieldMask` for updates** — distinguishes "not sent" from "set to empty"
4. **Always set deadlines** — unbound calls leak resources; 5-30s for most RPCs
5. **Enable reflection in dev** — makes debugging with grpcurl/grpcui easy
6. **Health checks on every service** — standard gRPC health protocol for load balancers
7. **Interceptors for cross-cutting concerns** — auth, logging, metrics, tracing
8. **Use streaming sparingly** — unary RPCs are simpler to debug and load-balance
9. **Version via package name** — `userservice.v1`, `userservice.v2`
10. **Keep messages small** — gRPC default max is 4MB; large payloads should be chunked or use streaming

## Common Pitfalls

- **No deadline**: Calls hang forever if server is slow — always set timeout
- **Reusing field numbers**: After deleting a field, `reserved` the number forever
- **Enum zero value**: Protobuf defaults to 0 — if 0 is meaningful, you'll get false matches
- **Blocking in async**: Python's `server.wait_for_termination()` blocks — handle signals properly
- **Browser direct calls**: Browsers can't do gRPC natively — need gRPC-Web proxy
- **Large messages**: Sending 100MB in one message → use client streaming with chunks
- **Missing health checks**: Kubernetes/load balancers need gRPC health protocol, not HTTP `/health`
