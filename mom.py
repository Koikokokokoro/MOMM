import os
import shutil
import subprocess
import json
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import ttk

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config.json')

# 默认配置
DEFAULT_CONFIG = {
    'original_dir': '',    # 原版游戏路径
    'mods_dir': '',        # MODs 文件夹路径
    'current_mod': None
}

# 加载/保存配置
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

config = load_config()

# 清单管理目录
MANIFEST_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'manifests')
os.makedirs(MANIFEST_DIR, exist_ok=True)

# 列出 Mods 列表
def list_mods():
    mods_dir = config['mods_dir']
    if not os.path.isdir(mods_dir):
        return ['原版']
    names = [n for n in os.listdir(mods_dir)
             if os.path.isdir(os.path.join(mods_dir, n)) and n != '__tmp_unpack__']
    return ['原版'] + names

# 应用并备份
def backup_and_apply(mod_name):
    orig = config['original_dir']
    if mod_name == '原版':
        prev = config.get('current_mod')
        if prev and prev != '原版':
            revert_mod(prev)
            config['current_mod'] = None
            save_config(config)
        return
    mod_path = os.path.join(config['mods_dir'], mod_name)
    if not os.path.isdir(orig) or not os.path.isdir(mod_path):
        raise FileNotFoundError('原版或 MOD 路径配置错误')
    prev = config.get('current_mod')
    if prev and prev != '原版':
        revert_mod(prev)
    manifest = {'mod_name': mod_name, 'added': [], 'overwritten': []}
    backup_folder = os.path.join(MANIFEST_DIR, mod_name)
    os.makedirs(backup_folder, exist_ok=True)
    for root, _, files in os.walk(mod_path):
        rel = os.path.relpath(root, mod_path)
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.join(orig, rel, f)
            rel_path = os.path.normpath(os.path.join(rel, f))
            if os.path.exists(dst):
                os.makedirs(os.path.join(backup_folder, 'backup', os.path.dirname(rel_path)), exist_ok=True)
                shutil.copy2(dst, os.path.join(backup_folder, 'backup', rel_path))
                manifest['overwritten'].append(rel_path)
            else:
                manifest['added'].append(rel_path)
            shutil.copy2(src, dst)
    with open(os.path.join(backup_folder, 'manifest.json'), 'w', encoding='utf-8') as mf:
        json.dump(manifest, mf, ensure_ascii=False, indent=2)
    config['current_mod'] = mod_name
    save_config(config)

# 回滚恢复
def revert_mod(mod_name):
    if not mod_name or mod_name == '原版':
        return
    orig = config['original_dir']
    backup_folder = os.path.join(MANIFEST_DIR, mod_name)
    manifest_file = os.path.join(backup_folder, 'manifest.json')
    if not os.path.exists(manifest_file):
        return
    with open(manifest_file, 'r', encoding='utf-8') as mf:
        manifest = json.load(mf)
    for rel in manifest['added']:
        p = os.path.join(orig, rel)
        if os.path.exists(p):
            os.remove(p)
    for rel in manifest['overwritten']:
        src = os.path.join(backup_folder, 'backup', rel)
        dst = os.path.join(orig, rel)
        if os.path.exists(src):
            shutil.copy2(src, dst)
    shutil.rmtree(backup_folder)
    config['current_mod'] = None
    save_config(config)

# 启动并等待游戏
class ModManagerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('红警 心灵终结 MOD 管理器')
        self.geometry('500x350')
        self.configure(bg='#2e2e2e')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TLabel', background='#2e2e2e', foreground='#ffffff', font=('Arial', 12))
        style.configure('TButton', font=('Arial', 11), padding=6)
        style.configure('Treeview', rowheight=24, font=('Arial', 11))
        style.map('Treeview', background=[('selected', '#4a90e2')], foreground=[('selected', '#ffffff')])

        menubar = tk.Menu(self)
        sm = tk.Menu(menubar, tearoff=0)
        sm.add_command(label='配置路径', command=self.open_settings)
        menubar.add_cascade(label='设置', menu=sm)
        self.config(menu=menubar)

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        ttk.Label(self, text='可用 Mods:').grid(row=0, column=0,
            sticky='nw', padx=20, pady=(10,0))
        self.tree = ttk.Treeview(self, columns=('Mod',), show='headings')
        self.tree.heading('Mod', text='Mod 名称')
        self.tree.grid(row=0, column=0, sticky='nsew',
            padx=20, pady=(35,10))

        frm = ttk.Frame(self)
        frm.grid(row=1, column=0, pady=10)
        ttk.Button(frm, text='刷新列表', command=self.refresh).grid(row=0, column=0, padx=5)
        ttk.Button(frm, text='添加 Mod', command=lambda: self.add_mod()).grid(row=0, column=1, padx=5)
        ttk.Button(frm, text='启动并应用', command=self.start_mod).grid(row=0, column=2, padx=5)
        ttk.Button(frm, text='删除 Mod', command=self.delete_mod).grid(row=0, column=3, padx=5)

        self.refresh()

    def disable_controls(self):
        self.tree.state(['disabled'])
        for widget in self.winfo_children():
            if isinstance(widget, ttk.Frame):
                for btn in widget.winfo_children(): btn.state(['disabled'])

    def enable_controls(self):
        self.tree.state(('!disabled',))
        for widget in self.winfo_children():
            if isinstance(widget, ttk.Frame):
                for btn in widget.winfo_children(): btn.state(('!disabled',))

    def refresh(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for m in list_mods(): self.tree.insert('', 'end', values=(m,))

    def start_mod(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning('提示', '请选择 Mod', parent=self)
            return
        mod = self.tree.item(sel[0], 'values')[0]
        backup_and_apply(mod)
        messagebox.showinfo('成功', f'已应用 Mod: {mod}', parent=self)
        exe = os.path.join(config['original_dir'], 'MentalOmegaClient.exe')
        if os.path.exists(exe):
            self.disable_controls()
            proc = subprocess.Popen([exe], cwd=config['original_dir'])
            self.withdraw()
            proc.wait()
            self.deiconify()
            self.enable_controls()

    def add_mod(self):
        add_mod_from_archive(self)

    def delete_mod(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning('提示', '请选择 Mod', parent=self)
            return
        mod = self.tree.item(sel[0], 'values')[0]
        if mod == '原版':
            messagebox.showwarning('禁止', '原版不能删除', parent=self)
            return
        if messagebox.askyesno('确认', f'确定要删除 Mod "{mod}" 吗？', parent=self):
            # 若当前已应用该 Mod，先回滚
            if config.get('current_mod') == mod:
                revert_mod(mod)
            path = os.path.join(config['mods_dir'], mod)
            if os.path.isdir(path): shutil.rmtree(path)
            # 清除 manifest
            mf = os.path.join(MANIFEST_DIR, mod)
            if os.path.isdir(mf): shutil.rmtree(mf)
            messagebox.showinfo('已删除', f'Mod "{mod}" 已删除', parent=self)
            config['current_mod'] = None
            save_config(config)
            self.refresh()

    def open_settings(self):
        w = tk.Toplevel(self)
        w.title('配置路径')
        w.geometry('520x240')
        w.configure(bg='#3e3e3e')
        w.transient(self)
        w.grab_set()
        w.attributes('-topmost', True)

        w.grid_rowconfigure(2, weight=1)
        w.grid_columnconfigure(1, weight=1)

        ttk.Label(w, text='原版目录:').grid(row=0, column=0,
            sticky='w', padx=20, pady=(15,5))
        o = ttk.Entry(w)
        o.insert(0, config.get('original_dir', ''))
        o.grid(row=0, column=1, sticky='ew', padx=10)
        ttk.Button(w, text='选择', command=lambda: self.select_dir(o)).grid(row=0, column=2, padx=10)

        ttk.Label(w, text='Mods 目录:').grid(row=1, column=0,
            sticky='w', padx=20, pady=(15,5))
        m = ttk.Entry(w)
        m.insert(0, config.get('mods_dir', ''))
        m.grid(row=1, column=1, sticky='ew', padx=10)
        ttk.Button(w, text='选择', command=lambda: self.select_dir(m)).grid(row=1, column=2, padx=10)

        def save_paths():
            o1, m1 = o.get().strip(), m.get().strip()
            if not os.path.isdir(o1):
                messagebox.showerror('错误', '原版目录无效', parent>w)
                return
            if not os.path.isdir(m1):
                messagebox.showerror('错误', 'Mods 目录无效', parent=w)
                return
            config['original_dir'], config['mods_dir'] = o1, m1
            save_config(config)
            messagebox.showinfo('保存', '已保存配置', parent=w)
            w.destroy()
            self.refresh()

        ttk.Button(w, text='保存', command=save_paths).grid(row=2, column=1, pady=20)

    def select_dir(self, entry):
        d = filedialog.askdirectory(parent=self)
        if d:
            entry.delete(0, tk.END)
            entry.insert(0, d)

# 压缩包解压支持
import subprocess as _subproc

def add_mod_from_archive(app):
    file_path = filedialog.askopenfilename(
        title='选择 Mod 压缩包',
        filetypes=[('Archives', '*.zip *.rar *.7z')],
        parent=app)
    if not file_path:
        return
    mods_dir = config['mods_dir']
    if not os.path.isdir(mods_dir):
        messagebox.showerror('错误', '请先在设置中配置 Mods 目录。', parent=app)
        return
    base = os.path.splitext(os.path.basename(file_path))[0]
    tmp = os.path.join(mods_dir, '__tmp_unpack__')
    try:
        if os.path.exists(tmp): shutil.rmtree(tmp)
        os.makedirs(tmp)
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.zip':
            shutil.unpack_archive(file_path, tmp)
        else:
            cmd = ['7z', 'x', file_path, f'-o{tmp}', '-y']
            res = _subproc.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(res.stderr or res.stdout)
        root = tmp
        while True:
            items = os.listdir(root)
            if len(items) == 1 and os.path.isdir(os.path.join(root, items[0])):
                root = os.path.join(root, items[0])
            else:
                break
        if not os.listdir(root): raise ValueError('空文件夹')
        name = os.path.basename(root) or base
        target = os.path.join(mods_dir, name)
        if os.path.exists(target):
            i = 1
            while os.path.exists(os.path.join(mods_dir, f'{name}_{i}')): i+=1
            target = os.path.join(mods_dir, f'{name}_{i}')
        shutil.move(root, target)
        shutil.rmtree(tmp)
        messagebox.showinfo('成功', f'已添加 Mod: {os.path.basename(target)}', parent=app)
        app.refresh()
    except Exception as e:
        if os.path.exists(tmp): shutil.rmtree(tmp)
        messagebox.showerror('解压失败', str(e), parent=app)

if __name__ == '__main__':
    app = ModManagerGUI()
    app.mainloop()
