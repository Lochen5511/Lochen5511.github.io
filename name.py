import os
from datetime import datetime

def create_user_file(user_name):
    """
    建立使用者名字的文字檔
    
    參數:
        user_name: 使用者名字
    
    回傳:
        成功返回 True 和檔案路徑，失敗返回 False 和錯誤訊息
    """
    try:
        # 檢查名字是否為空
        if not user_name or user_name.strip() == '':
            return False, '名字不可為空'
        
        user_name = user_name.strip()
        
        # 建立 log 資料夾（如果不存在）
        log_dir = r'C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\log'
        os.makedirs(log_dir, exist_ok=True)
        
        # 建立使用者檔案
        file_path = os.path.join(log_dir, f'{user_name}.txt')
        
        # 寫入檔案
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f'使用者名稱: {user_name}\n')
            f.write(f'建立時間: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        
        return True, file_path
    
    except Exception as e:
        return False, f'建立檔案時發生錯誤: {str(e)}'


# 如果直接執行此檔案，可以測試功能
if __name__ == '__main__':
    # 測試功能
    test_name = input('請輸入測試名字: ')
    success, result = create_user_file(test_name)
    
    if success:
        print(f'✓ 成功建立檔案: {result}')
    else:
        print(f'✗ 失敗: {result}')