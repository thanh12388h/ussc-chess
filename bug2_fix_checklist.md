# CHECKLIST FIX LỖI #2 (Verify fail sau khi cược/pass)

## Mục tiêu
- Không còn lỗi: `Xác nhận thất bại - Dữ liệu chưa được lưu`.
- User không cần spam Cược/PASS.
- Dữ liệu bid/pass luôn có trên Firestore sau submit.

## 1) Chặn clobber write (ghi đè toàn bộ auctionState)
- [x] Thêm helper `persistAuctionStatePatch` để chỉ ghi field cần thiết.
- [x] Đổi `set(auctionState)` ở luồng timer sang patch update (`timeLeft`, `running`, `review`).
- [x] Đổi `set(auctionState)` ở luồng reset/next round/restart/clear data sang patch có chủ đích.
- [x] Đổi admin helper `placeBid/passRound/updateTeamReview` từ full set sang field-level update.
- [x] Đổi force-sync chỉ cập nhật `roundData` (không đè bids/answers/teamReview).

## 2) Cứng hóa submit bid/pass
- [x] `placeAuctionBid` dùng `runTransaction` + `mutationId`.
- [x] `passAuctionBid` dùng `runTransaction` + `mutationId`.
- [x] Verify sau commit có retry (`verifyBidWrite`) thay vì đọc 1 lần.
- [x] Rollback local chỉ khi commit/verify fail thật sự.

## 3) Script debug tự chạy
- [x] Tạo file `bug2_auto_debug.py`.
- [x] Chạy smoke 10 vòng liên tiếp không fail.
- [ ] Chạy stress 50 vòng liên tiếp không fail.

## 4) Tiêu chí DONE
- [ ] 0 lỗi verify fail trong stress run >= 50 vòng.
- [ ] Bid/PASS đều đồng bộ local/server trong mọi vòng test.
- [ ] Không còn trường hợp cần spam thao tác.

## Lệnh chạy
```bash
py bug2_auto_debug.py --iterations 10
py bug2_auto_debug.py --iterations 50
```

## Ghi chú
- Script tạo user/team test mới theo timestamp để tránh đụng dữ liệu cũ.
- Nếu Firebase chặn quyền ghi, script sẽ fail sớm và in nguyên nhân cụ thể.
