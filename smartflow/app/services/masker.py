"""
脱敏服务

功能：对 AI 回复中的敏感信息（手机号/身份证/银行卡）自动打码。
"""
import re

def mask_sensitive(text: str) -> str:
    if not text:
        return text
    # 手机号：138****1234
    text = re.sub(r'1[3-9]\d{9}', lambda m: m.group()[:3] + '****' + m.group()[-4:], text)
    # 身份证：1101**********1234
    text = re.sub(r'\d{17}[\dXx]', lambda m: m.group()[:4] + '**********' + m.group()[-4:], text)
    # 银行卡：6222****1234
    text = re.sub(r'\d{16,19}', lambda m: m.group()[:4] + '****' + m.group()[-4:], text)
    return text