//! pack-plugin —— 将 plugin/astrbot/ 打包为 AstrBot 可安装的插件 zip。
//!
//! 用法（任选其一，均会自动编译依赖后执行）：
//!   cargo run  --features pack-plugin --bin pack-plugin
//!   cargo alias：cargo plugin-pack   （见 .cargo/config.toml）
//!
//! 输出：<项目根>/dist/astrbot_plugin_warframe_helper.zip
//! zip 内为插件文件平铺（解压到 AstrBot/data/plugins/astrbot_plugin_warframe_helper/ 即安装）。

use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use zip::write::FileOptions;
use zip::CompressionMethod;

fn main() {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let plugin_dir = manifest.join("plugin").join("astrbot");
    let dist_dir = manifest.join("dist");

    if !plugin_dir.is_dir() {
        eprintln!("[error] 插件目录不存在: {}", plugin_dir.display());
        std::process::exit(1);
    }
    fs::create_dir_all(&dist_dir).expect("创建 dist 目录失败");
    let out_path = dist_dir.join("astrbot_plugin_warframe_helper.zip");

    // 收集文件（排除 .git / __pycache__ / pyc / 本工具产物）
    let mut files: Vec<PathBuf> = Vec::new();
    collect(&plugin_dir, &plugin_dir, &mut files);
    files.sort(); // 稳定顺序，保证可复现

    if files.is_empty() {
        eprintln!("[error] 插件目录为空: {}", plugin_dir.display());
        std::process::exit(1);
    }

    let file = fs::File::create(&out_path).expect("创建 zip 失败");
    let mut zip = zip::ZipWriter::new(file);
    // AstrBot 面板/主流平台均可读 Deflate；unix 权限保留可执行位无必要
    let opts = FileOptions::default()
        .compression_method(CompressionMethod::Deflated)
        .unix_permissions(0o644);

    let mut total_raw: u64 = 0;
    for path in &files {
        let rel = path.strip_prefix(&plugin_dir).expect("strip prefix");
        let name = rel.to_string_lossy().replace('\\', "/");
        if path.is_dir() {
            zip.add_directory(name, opts).expect("add_directory 失败");
            continue;
        }
        let data = read_file(path);
        total_raw += data.len() as u64;
        zip.start_file(name, opts).expect("start_file 失败");
        zip.write_all(&data).expect("写入 zip 失败");
    }
    let out_file = zip.finish().expect("finish zip 失败");

    let size = out_file.metadata().map(|m| m.len()).unwrap_or(0);
    println!("[pack] 文件数 : {}", files.len());
    println!("[pack] 原始   : {:.1} KB", total_raw as f64 / 1024.0);
    println!(
        "[pack] 压缩后 : {:.1} KB → {}",
        size as f64 / 1024.0,
        out_path.display()
    );
}

/// 递归收集，跳过无关目录与编译缓存
fn collect(root: &Path, dir: &Path, out: &mut Vec<PathBuf>) {
    let entries = match fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return,
    };
    for entry in entries.flatten() {
        let p = entry.path();
        let name = entry.file_name();
        let name = name.to_string_lossy();
        if p.is_dir() {
            if matches!(name.as_ref(), ".git" | "__pycache__" | "dist" | "temp" | "node_modules") {
                continue;
            }
            collect(root, &p, out);
        } else if name.ends_with(".pyc") || name.ends_with(".pyo") || name == ".DS_Store" || name == ".gitignore" {
            continue;
        } else {
            out.push(p);
        }
    }
}

fn read_file(p: &Path) -> Vec<u8> {
    let mut f = fs::File::open(p).expect("打开文件失败");
    let mut buf = Vec::new();
    f.read_to_end(&mut buf).expect("读取失败");
    buf
}
