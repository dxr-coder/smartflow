"""
数据清洗服务

功能：去除噪声、去重、格式标准化。
"""
import re


def clean_text(text: str) -> str:
    """文本清洗主函数"""
    text = remove_noise(text)
    text = normalize_whitespace(text)
    text = deduplicate_lines(text)
    return text.strip()


def remove_noise(text: str) -> str:
    """去除噪声：特殊字符、乱码、多余符号"""
    # 去除连续特殊字符（保留中文、英文、数字、常用标点）
    text = re.sub(r'[^\w一-鿿\s。！？、，；：“”‘’（）【】《》.,!?;:/=+\-[\]{}`~@#$%^&*<>|\\]', '', text)
    # 去除乱码（连续不可见字符）
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text


def normalize_whitespace(text: str) -> str:
    """标准化空白字符"""
    # 换行符统一
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # 连续空行合并为一个
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 行内多余空格合并
    text = re.sub(r'[ \t]+', ' ', text)
    return text


def deduplicate_lines(text: str) -> str:
    """行级去重（去掉完全重复的行）"""
    lines = text.split('\n')
    seen = set()
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped and stripped in seen:
            continue
        seen.add(stripped)
        result.append(line)
    return '\n'.join(result)
