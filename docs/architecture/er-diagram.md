# ER 图

五层记忆的持久化 schema（迁移见 `database/migrations/versions/0001_initial_schema.py`）。

```mermaid
erDiagram
    users ||--o| profiles : "1:1 (Layer 1)"
    users ||--o{ daily_logs : "1:N (Layer 2)"
    users ||--o{ insights : "1:N (Layer 3)"
    users ||--o{ strategies : "1:N (Layer 4)"
    users ||--o{ evolution_logs : "1:N (Layer 5, nullable)"

    users {
        uuid id PK
        string email UK
        timestamptz created_at
    }

    profiles {
        uuid id PK
        uuid user_id FK "UNIQUE, CASCADE"
        int age "1-149"
        string sex
        float height_cm
        float weight_kg
        text goal
        jsonb constraints
    }

    daily_logs {
        uuid id PK
        uuid user_id FK "CASCADE"
        date date "UNIQUE(user_id, date)"
        jsonb workout
        jsonb nutrition
        float sleep_hours "0-24"
        int mood "1-10"
        int steps ">=0"
        text recovery_note
    }

    insights {
        uuid id PK
        uuid user_id FK "CASCADE"
        text content
        string category
        float confidence "0-1"
        string source
        timestamptz created_at
        vector embedding "1536维, HNSW cosine 索引"
    }

    strategies {
        uuid id PK
        uuid user_id FK "CASCADE"
        string domain
        text content
        bool active
        timestamptz created_at
    }

    evolution_logs {
        uuid id PK
        uuid user_id FK "SET NULL, 系统级变更可为空"
        string change_type
        jsonb before
        jsonb after
        text reason
        timestamptz created_at
    }
```

## 设计要点

- **约束下沉到数据库**：mood 1-10、confidence 0-1、sleep 0-24 等既在 Pydantic 校验，也以 CHECK 约束落库——任何绕过应用层的写入同样受约束（Data First）。
- **`daily_logs` 每用户每天一行**（`UNIQUE(user_id, date)`），日内多事件在 `workout`/`nutrition` JSONB 内累积，保持 Layer 2 append-only 语义。
- **`insights.embedding`**：`vector(1536)` + HNSW 余弦索引，支撑 `core/memory` 的语义召回。
- **`evolution_logs.user_id` 可空**（`ON DELETE SET NULL`）：系统级演进不绑定用户，且用户删除后演进记录仍保留供回放。
