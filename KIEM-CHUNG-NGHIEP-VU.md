# Hướng dẫn kiểm chứng nghiệp vụ — Bookmarks API

> Tài liệu này hướng dẫn **cách kiểm chứng (verify)** rằng phần mềm đáp ứng đúng các
> yêu cầu nghiệp vụ mô tả trong [`ASSESSMENT.md`](ASSESSMENT.md).
> Mỗi yêu cầu đều có **2 cách kiểm chứng**: chạy **test tự động** và **thao tác thủ công**
> (qua Swagger UI hoặc `curl`).

- Base URL: `http://127.0.0.1:8000`
- Tài liệu tương tác (Swagger): `http://127.0.0.1:8000/docs`
- Mọi lỗi đều trả về theo cấu trúc nhất quán: `{ "error": { "code", "message", "details" } }`
- Tài khoản mẫu (sau khi nạp dữ liệu): `alice@example.com` / `password123` và `bob@example.com` / `password123`

> Ghi chú: phần mã nguồn đã được tái cấu trúc theo **repository pattern**
> (router → service → repository, mỗi tầng có interface). **Hành vi nghiệp vụ không đổi**
> so với mô tả trong `ASSESSMENT.md`; chỉ vị trí code thay đổi (xem `README.md`).

---

## 0. Mục đích

`ASSESSMENT.md` mô tả một **Bookmarks API**: dịch vụ backend cho phép người dùng **lưu, gắn
thẻ (tag), tìm kiếm và quản lý** các bookmark web. Các nhóm yêu cầu nghiệp vụ chính:

1. **Đăng ký & đăng nhập** (xác thực bằng JWT).
2. **Phân quyền theo chủ sở hữu** — người dùng chỉ thấy/sửa bookmark của chính mình.
3. **CRUD bookmark** (URL, tiêu đề, mô tả).
4. **Gắn nhiều tag** cho bookmark (quan hệ nhiều-nhiều).
5. **Tìm kiếm & lọc** theo tag, từ khoá tiêu đề, khoảng ngày; có **phân trang**.
6. **Thống kê** tổng hợp bằng **SQL thuần (raw SQL)**.
7. **Tài liệu API** OpenAPI/Swagger tại `/docs`.
8. **Kiểm tra đầu vào (validation)** và **xử lý lỗi nhất quán**.
9. **Tầng dữ liệu**: CSDL miễn phí, có **migration**, tối thiểu 3 bảng, quan hệ nhiều-nhiều.

---

## 1. Chuẩn bị môi trường

Chọn **một** trong hai cách.

### Cách A — Chạy cục bộ (SQLite)

```bash
make install                      # tạo .venv + cài phụ thuộc (hoặc: pip install -r requirements-dev.txt)
source .venv/bin/activate
export DATABASE_URL="sqlite:///./bookmarks.db"
export JWT_SECRET="khoa-bi-mat-cuc-bo-0123456789-abcdefghij"
alembic upgrade head              # tạo schema từ migration
python -m scripts.seed            # nạp dữ liệu mẫu
uvicorn app.main:app --reload     # chạy server
```

### Cách B — Chạy bằng Podman (PostgreSQL)

```bash
make up                                            # build + chạy API + PostgreSQL
podman-compose exec -T api python -m scripts.seed  # nạp dữ liệu mẫu
```

Kiểm tra server đã sống:

```bash
curl -s http://127.0.0.1:8000/health
# Kỳ vọng: {"status":"ok"}
```

---

## 2. Kiểm chứng nhanh toàn bộ bằng test tự động

Đây là cách nhanh nhất để khẳng định toàn bộ nghiệp vụ vẫn đúng:

```bash
make check        # = lint + test  → Kỳ vọng: "All checks passed!" và 59 passed
make cov          # test kèm báo cáo coverage → Kỳ vọng: ~96%
```

Bộ test ánh xạ trực tiếp tới các yêu cầu nghiệp vụ:

| Tệp test | Yêu cầu nghiệp vụ được kiểm chứng |
|----------|-----------------------------------|
| `tests/test_auth.py`       | Đăng ký, đăng nhập, JWT, trùng email (409), sai mật khẩu (401), token hết hạn/sai loại. |
| `tests/test_bookmarks.py`  | CRUD, validation, chuẩn hoá tag, **phân quyền theo chủ sở hữu**. |
| `tests/test_search.py`     | Lọc theo `tag`, từ khoá `q`, khoảng ngày; phân trang (offset + cursor). |
| `tests/test_stats.py`      | Thống kê bằng raw SQL (tổng, top tag, theo tháng), tách biệt theo người dùng. |
| `tests/test_errors.py`     | Cấu trúc lỗi nhất quán cho mọi loại lỗi. |
| `tests/test_openapi.py`    | OpenAPI hợp lệ, Swagger phục vụ tại `/docs`, đáp ứng khớp schema. |
| `tests/test_migrations.py` | Migration chạy sạch (lên/xuống), không lệch model. |
| `tests/test_cascade.py`    | Xoá user xoá lan (cascade) sang bookmark + bảng liên kết. |
| `tests/test_etag.py`       | Chống ghi đè (race condition) bằng ETag/`If-Match`: 428/412/200, ngăn lost-update. |
| `tests/test_services.py`   | Tầng nghiệp vụ (service) kiểm thử độc lập với repository giả. |

---

## 3. Kiểm chứng từng yêu cầu nghiệp vụ (thủ công)

Mỗi bước nêu **lệnh** và **kết quả kỳ vọng**. Trước hết lấy token đăng nhập của `alice`:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"password123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
echo "$TOKEN"     # phải in ra một chuỗi JWT gồm 3 phần ngăn bởi dấu chấm
```

### 3.1 Đăng ký & Đăng nhập (JWT) — *Yêu cầu: Users & Auth*

```bash
# Đăng ký người dùng mới
curl -s -X POST http://127.0.0.1:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"tester","email":"tester@example.com","password":"password123"}'
```
✅ **201**, trả về `{ "user": {...}, "token": "...", "token_type": "bearer" }`.
✅ Phản hồi **không** chứa mật khẩu hay `password_hash`.

```bash
# Đăng nhập sai mật khẩu
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"sai-mat-khau"}'
```
✅ **401**, mã lỗi `AUTHENTICATION_ERROR`, thông điệp chung chung (không lộ email có tồn tại hay không).

### 3.2 Phân quyền theo chủ sở hữu — *Yêu cầu: chỉ thấy bookmark của mình*

```bash
# Lấy token của bob
BTOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"bob@example.com","password":"password123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# bob cố đọc bookmark của alice (ví dụ id=2)
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/bookmarks/2 \
  -H "Authorization: Bearer $BTOKEN"
```
✅ **404** (không phải 403) — API không bao giờ tiết lộ rằng bookmark của người khác tồn tại.

```bash
# Gọi API bookmark mà không có token
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/bookmarks
```
✅ **401** — mọi route `/api/bookmarks*` đều bắt buộc xác thực.

### 3.3 CRUD bookmark — *Yêu cầu: CRUD (URL, title, description)*

```bash
# CREATE — tạo bookmark
curl -s -X POST http://127.0.0.1:8000/api/bookmarks \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"url":"https://news.ycombinator.com","title":"Hacker News","description":"tin công nghệ","tags":["News","Tech","news"]}'
```
✅ **201**; ghi lại `id` trong phản hồi. `tags` trả về `["news","tech"]` (đã viết thường + bỏ trùng).

```bash
# READ — đọc 1 bookmark (thay <id> bằng id vừa tạo)
curl -s http://127.0.0.1:8000/api/bookmarks/<id> -H "Authorization: Bearer $TOKEN"

# UPDATE — cập nhật 1 phần, thay toàn bộ tag
curl -s -X PUT http://127.0.0.1:8000/api/bookmarks/<id> \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Tiêu đề mới","tags":["sql","backend"]}'

# DELETE — xoá
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE http://127.0.0.1:8000/api/bookmarks/<id> \
  -H "Authorization: Bearer $TOKEN"
```
✅ READ **200**; UPDATE **200** (tiêu đề đổi, `tags` thành `["backend","sql"]`, `updated_at` tăng);
DELETE **204**, sau đó READ lại id đó trả **404**.

### 3.4 Gắn nhiều tag (quan hệ nhiều-nhiều) — *Yêu cầu: tag with one or more tags*

Quan sát ở bước 3.3: gửi `["News","Tech","news"]` nhưng nhận lại `["news","tech"]`.
✅ Một bookmark có **nhiều tag**; tag được **chuẩn hoá** (viết thường, bỏ trùng) và **dùng chung**
giữa các bookmark (bảng liên kết nhiều-nhiều `bookmark_tags`).

### 3.5 Tìm kiếm & lọc — *Yêu cầu: filter & search by tag, keyword, date range*

```bash
# Lọc theo tag
curl -s "http://127.0.0.1:8000/api/bookmarks?tag=python" -H "Authorization: Bearer $TOKEN"

# Tìm theo từ khoá (trong tiêu đề + mô tả, không phân biệt hoa thường)
curl -s "http://127.0.0.1:8000/api/bookmarks?q=docs" -H "Authorization: Bearer $TOKEN"

# Lọc theo khoảng ngày (UTC, bao gồm hai đầu mút)
curl -s "http://127.0.0.1:8000/api/bookmarks?from=2025-03-01&to=2025-03-31" \
  -H "Authorization: Bearer $TOKEN"

# Kết hợp nhiều điều kiện
curl -s "http://127.0.0.1:8000/api/bookmarks?tag=python&q=fast" -H "Authorization: Bearer $TOKEN"
```
✅ Lần lượt trả về đúng tập kết quả: chỉ bookmark có tag `python`; chỉ bookmark khớp từ khoá;
chỉ bookmark tạo trong tháng 3/2025; và giao của các điều kiện khi kết hợp.

### 3.6 Phân trang — *Yêu cầu: pagination*

```bash
# Phân trang theo offset
curl -s "http://127.0.0.1:8000/api/bookmarks?page=1&per_page=3" -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['pagination'])"
```
✅ `pagination` có đủ `page`, `per_page`, `total` (tổng số bản ghi khớp), `total_pages`,
`has_next`, `has_prev`.

```bash
# Phân trang theo con trỏ (cursor / keyset — tính năng bonus)
curl -s "http://127.0.0.1:8000/api/bookmarks?per_page=3&cursor=999999" -H "Authorization: Bearer $TOKEN"
# lấy pagination.next_cursor rồi gọi trang kế:
curl -s "http://127.0.0.1:8000/api/bookmarks?per_page=3&cursor=<next_cursor>" -H "Authorization: Bearer $TOKEN"
```
✅ Các trang không trùng nhau; trang cuối trả `next_cursor: null` và `has_next: false`.

### 3.6b Chống tranh chấp ghi đè (ETag / If-Match) — *Yêu cầu: tránh race condition khi sửa đồng thời*

```bash
# Lấy ETag hiện tại của bookmark 1
ETAG=$(curl -s -D - -o /dev/null "http://127.0.0.1:8000/api/bookmarks/1" \
  -H "Authorization: Bearer $TOKEN" | awk -F': ' 'tolower($1)=="etag"{print $2}' | tr -d '\r')
echo "ETag = $ETAG"

# (a) Sửa mà KHÔNG kèm If-Match
curl -s -o /dev/null -w '%{http_code}\n' -X PUT "http://127.0.0.1:8000/api/bookmarks/1" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"title":"x"}'
```
✅ **428** (`PRECONDITION_REQUIRED`) — bắt buộc gửi `If-Match`.

```bash
# (b) Sửa với If-Match cũ/sai
curl -s -o /dev/null -w '%{http_code}\n' -X PUT "http://127.0.0.1:8000/api/bookmarks/1" \
  -H "Authorization: Bearer $TOKEN" -H 'If-Match: "999"' -H 'Content-Type: application/json' -d '{"title":"x"}'
```
✅ **412** (`PRECONDITION_FAILED`) — bản ghi đã bị người khác đổi.

```bash
# (c) Sửa với ETag đúng → thành công, version tăng
curl -s -X PUT "http://127.0.0.1:8000/api/bookmarks/1" \
  -H "Authorization: Bearer $TOKEN" -H "If-Match: $ETAG" \
  -H 'Content-Type: application/json' -d '{"title":"Đã cập nhật có điều kiện"}'
```
✅ **200**; trường `version` tăng và trả về `ETag` mới. Dùng lại `ETAG` cũ sẽ bị **412** —
đây chính là cơ chế **ngăn mất cập nhật (lost update)** khi hai người sửa cùng lúc.

> Cơ chế bảo vệ ở **2 lớp**: (1) tầng ứng dụng so khớp `If-Match` với `version` hiện tại;
> (2) tầng CSDL dùng cột `version` (`version_id_col`) khiến câu `UPDATE ... WHERE version = <kỳ vọng>`
> mang tính nguyên tử — nếu có giao dịch khác ghi xen vào, lệnh sẽ thất bại và trả **412**.

### 3.7 Thống kê (raw SQL) — *Yêu cầu: stats endpoint*

```bash
curl -s http://127.0.0.1:8000/api/bookmarks/stats -H "Authorization: Bearer $TOKEN"
```
✅ Trả về `{ "total_bookmarks", "total_tags", "top_tags":[{name,count}], "bookmarks_per_month":[{month,count}] }`.
✅ Số liệu chỉ tính trên bookmark của chính người dùng (đăng nhập bob sẽ ra số khác).

### 3.8 Tài liệu API (OpenAPI/Swagger) — *Yêu cầu: docs at /docs*

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/docs          # → 200 (Swagger UI)
curl -s http://127.0.0.1:8000/openapi.json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['openapi'], len(d['paths']),'paths')"
# → 3.1.0  7 paths
```
✅ Mở trình duyệt vào `/docs`: thấy đầy đủ endpoint, schema request/response, mã trạng thái,
và nút **Authorize** để nhập JWT (yêu cầu xác thực được ghi rõ trong spec).

### 3.9 Validation & lỗi nhất quán — *Yêu cầu: input validation + consistent JSON errors*

```bash
# URL không hợp lệ
curl -s -X POST http://127.0.0.1:8000/api/bookmarks \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"url":"khong-phai-url","title":"x"}'
```
✅ **422**, body: `{"error":{"code":"VALIDATION_ERROR","message":"url: ...","details":{"field":"url",...}}}`.

```bash
# Đăng ký trùng email
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"password123"}'
```
✅ **409** (`CONFLICT`). Mọi loại lỗi (401/404/409/422/429/500) đều theo **cùng một cấu trúc** `{ "error": {...} }`.

### 3.10 Tầng dữ liệu: CSDL, migration, 3 bảng, M2M — *Yêu cầu: data layer*

```bash
# Migration chạy sạch cả lên lẫn xuống (trên SQLite tạm)
DATABASE_URL="sqlite:///./_check.db" alembic upgrade head
DATABASE_URL="sqlite:///./_check.db" alembic check        # → "No new upgrade operations detected" (model khớp migration)
DATABASE_URL="sqlite:///./_check.db" alembic downgrade base
rm -f _check.db
```
✅ Có **migration** chạy không lỗi và **không lệch** so với model.

```bash
# Kiểm tra tồn tại tối thiểu 3 bảng + bảng liên kết nhiều-nhiều (trên DB đã seed)
python3 -c "import sqlite3; c=sqlite3.connect('bookmarks.db'); print([r[0] for r in c.execute(\"select name from sqlite_master where type='table' order by name\")])"
```
✅ Thấy `users`, `bookmarks`, `tags` và bảng liên kết `bookmark_tags` (quan hệ nhiều-nhiều).

> Với Podman/PostgreSQL, kiểm tra bảng bằng:
> `podman-compose exec -T db psql -U bookmarks -d bookmarks -c "\dt"`

---

## 4. Bảng đối chiếu: yêu cầu nghiệp vụ ↔ cách kiểm chứng

| # | Yêu cầu trong ASSESSMENT.md | Test tự động | Kiểm chứng thủ công |
|---|------------------------------|--------------|---------------------|
| 1 | Đăng ký & đăng nhập (JWT) | `test_auth.py` | Mục 3.1 |
| 2 | Chỉ thấy/sửa bookmark của mình | `test_bookmarks.py` (ownership) | Mục 3.2 |
| 3 | CRUD bookmark (URL, title, description) | `test_bookmarks.py` | Mục 3.3 |
| 4 | Gắn nhiều tag (M2M) | `test_bookmarks.py`, `test_cascade.py` | Mục 3.4 |
| 5 | Tìm kiếm & lọc (tag, từ khoá, ngày) | `test_search.py` | Mục 3.5 |
| 6 | Phân trang | `test_search.py` | Mục 3.6 |
| 6b | Chống race condition (ETag/If-Match) | `test_etag.py` | Mục 3.6b |
| 7 | Thống kê bằng raw SQL | `test_stats.py` | Mục 3.7 |
| 8 | Tài liệu OpenAPI/Swagger tại `/docs` | `test_openapi.py` | Mục 3.8 |
| 9 | Validation + lỗi nhất quán | `test_errors.py`, `test_openapi.py` | Mục 3.9 |
| 10 | CSDL + migration + ≥3 bảng + M2M | `test_migrations.py`, `test_cascade.py` | Mục 3.10 |
| 11 | ≥10 test (happy path, biên, auth, hợp đồng OpenAPI) | Toàn bộ `tests/` (**47 test**) | `make test` |

---

## 5. Checklist nhanh

- [ ] `make check` → lint sạch + **59 passed**
- [ ] `make cov` → coverage ~96%
- [ ] `/health` trả `{"status":"ok"}`
- [ ] Đăng ký (201) / đăng nhập (200) / sai mật khẩu (401) / trùng email (409)
- [ ] Không token → 401; bookmark người khác → 404 (phân quyền)
- [ ] Tạo / đọc / sửa / xoá bookmark hoạt động (201/200/200/204)
- [ ] Gắn nhiều tag, tag được chuẩn hoá + bỏ trùng
- [ ] Lọc theo `tag`, `q`, khoảng ngày; phân trang offset + cursor
- [ ] Chống race condition: PUT/DELETE thiếu `If-Match` → 428; sai → 412; đúng → 200/204
- [ ] `/api/bookmarks/stats` trả tổng + top tag + theo tháng
- [ ] `/docs` và `/openapi.json` truy cập được, có Authorize (JWT)
- [ ] Lỗi luôn theo cấu trúc `{ "error": { code, message, details } }`
- [ ] Migration chạy sạch; có đủ bảng `users`, `bookmarks`, `tags`, `bookmark_tags`

---

> Tài liệu liên quan: [`ASSESSMENT.md`](ASSESSMENT.md) (đề bài + checklist), [`README.md`](README.md)
> (cài đặt & kiến trúc), [`TESTING.md`](TESTING.md) (hướng dẫn kiểm thử chi tiết bằng tiếng Anh).
