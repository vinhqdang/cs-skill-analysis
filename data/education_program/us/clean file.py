import pandas as pd

# File master đầy đủ 10 cột đã cứu ở bước trước
INPUT_FILE = "master_courses_rescued_full.csv"

print("[-] Đang nạp dữ liệu từ file master...")
df = pd.read_csv(INPUT_FILE)

# Chuẩn hóa cột domain (chuyển chữ thường, xóa khoảng trắng thừa) để lọc không bị sót
df['university_domain'] = df['university_domain'].astype(str).str.strip().str.lower()

print("[-] Bắt đầu phân loại dữ liệu theo quốc gia...")

# Lọc UK: Lấy các trường có domain kết thúc bằng '.uk' (như .ac.uk)
df_uk = df[df['university_domain'].str.endswith('.uk')]

# Lọc US: Lấy các trường có domain kết thúc bằng '.edu'
df_us = df[df['university_domain'].str.endswith('.edu')]

# Kiểm đếm số lượng dòng
print(f"[+] Phân loại thành công khu vực UK: {len(df_uk)} môn.")
print(f"[+] Phân loại thành công khu vực US: {len(df_us)} môn.")

# Kiểm tra xem có dòng nào bị "lọt lưới" do lỗi domain không
orphans = len(df) - (len(df_uk) + len(df_us))
if orphans > 0:
    print(f"[!] Cảnh báo: Phát hiện {orphans} dòng có domain dị, không thuộc .edu cũng không thuộc .uk!")

# Xuất ra 2 file riêng biệt
df_uk.to_csv("master_courses_uk.csv", index=False)
df_us.to_csv("master_courses_us.csv", index=False)

print("\n[+] HOÀN THÀNH BÀI TOÁN! Bác kiểm tra 2 file mới xuất hiện trong thư mục nhé:")
print("   -> 'master_courses_uk.csv' (Môn học các trường Anh)")
print("   -> 'master_courses_us.csv' (Môn học các trường Mỹ)")