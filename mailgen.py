#!/usr/bin/env python3
import os
import sys
import json
import csv
import re
import shutil
import zipfile
import hashlib
import difflib
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional

import click
from jinja2 import Environment, BaseLoader, TemplateSyntaxError, nodes, TemplateNotFound
from jinja2.ext import Extension
import markdown as md_lib
from bs4 import BeautifulSoup
from tabulate import tabulate
from colorama import init, Fore, Style, Back
from premailer import Premailer

init(autoreset=True)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.mailgen_data')
TEMPLATES_FILE = os.path.join(DATA_DIR, 'templates.json')
FRAGMENTS_FILE = os.path.join(DATA_DIR, 'fragments.json')
VERSIONS_DIR = os.path.join(DATA_DIR, 'versions')
SEND_LOG_FILE = os.path.join(DATA_DIR, 'send_log.json')
STATS_FILE = os.path.join(DATA_DIR, 'stats.json')
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

for d in [DATA_DIR, VERSIONS_DIR, OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)


HTML_THEMES = {
    'business': {
        'name': '商务',
        'css': '''
            body { font-family: 'Helvetica Neue', Arial, sans-serif; background: #f5f7fa; margin: 0; padding: 20px; }
            .email-container { max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 6px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); overflow: hidden; }
            .email-header { background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%); color: #ffffff; padding: 30px 40px; }
            .email-header h1 { margin: 0; font-size: 24px; font-weight: 600; }
            .email-body { padding: 40px; color: #2d3748; line-height: 1.7; }
            .email-body h1, .email-body h2, .email-body h3 { color: #1a365d; margin-top: 0; }
            .email-body p { margin: 0 0 16px 0; }
            .email-body ul, .email-body ol { margin: 0 0 16px 20px; padding: 0; }
            .email-body li { margin-bottom: 8px; }
            .email-body a { color: #2b6cb0; text-decoration: none; }
            .email-body code { background: #edf2f7; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
            .email-body pre { background: #1a202c; color: #e2e8f0; padding: 16px; border-radius: 4px; overflow-x: auto; }
            .email-body pre code { background: none; padding: 0; color: inherit; }
            .email-body blockquote { border-left: 4px solid #2b6cb0; margin: 16px 0; padding: 10px 20px; background: #f7fafc; color: #4a5568; }
            .email-body table { border-collapse: collapse; width: 100%; margin: 16px 0; }
            .email-body th, .email-body td { border: 1px solid #e2e8f0; padding: 12px; text-align: left; }
            .email-body th { background: #f7fafc; font-weight: 600; }
            .btn { display: inline-block; background: #2b6cb0; color: #ffffff !important; padding: 12px 32px; border-radius: 4px; text-decoration: none; font-weight: 500; }
            .email-footer { background: #f7fafc; padding: 24px 40px; color: #718096; font-size: 13px; text-align: center; border-top: 1px solid #e2e8f0; }
        '''
    },
    'minimal': {
        'name': '简约',
        'css': '''
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #ffffff; margin: 0; padding: 20px; }
            .email-container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; }
            .email-header { padding: 32px 32px 16px 32px; border-bottom: 1px solid #e5e7eb; }
            .email-header h1 { margin: 0; font-size: 20px; font-weight: 500; color: #111827; }
            .email-body { padding: 32px; color: #374151; line-height: 1.6; }
            .email-body h1, .email-body h2, .email-body h3 { color: #111827; margin-top: 0; font-weight: 500; }
            .email-body p { margin: 0 0 16px 0; }
            .email-body ul, .email-body ol { margin: 0 0 16px 24px; padding: 0; }
            .email-body li { margin-bottom: 8px; }
            .email-body a { color: #2563eb; text-decoration: none; }
            .email-body code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 0.875em; }
            .email-body pre { background: #1f2937; color: #f9fafb; padding: 16px; border-radius: 6px; overflow-x: auto; }
            .email-body pre code { background: none; padding: 0; color: inherit; }
            .email-body blockquote { border-left: 3px solid #d1d5db; margin: 16px 0; padding: 8px 16px; color: #6b7280; }
            .email-body table { border-collapse: collapse; width: 100%; margin: 16px 0; }
            .email-body th, .email-body td { border-bottom: 1px solid #e5e7eb; padding: 12px 8px; text-align: left; }
            .email-body th { color: #111827; font-weight: 500; }
            .btn { display: inline-block; background: #111827; color: #ffffff !important; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-weight: 500; }
            .email-footer { padding: 24px 32px; color: #9ca3af; font-size: 12px; text-align: center; border-top: 1px solid #e5e7eb; }
        '''
    },
    'colorful': {
        'name': '彩色',
        'css': '''
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; padding: 30px; min-height: 100vh; }
            .email-container { max-width: 620px; margin: 0 auto; background: #ffffff; border-radius: 16px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); overflow: hidden; }
            .email-header { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: #ffffff; padding: 36px 40px; }
            .email-header h1 { margin: 0; font-size: 28px; font-weight: 700; }
            .email-body { padding: 40px; color: #334155; line-height: 1.8; }
            .email-body h1, .email-body h2, .email-body h3 { margin-top: 0; }
            .email-body h1 { color: #be185d; }
            .email-body h2 { color: #7c3aed; }
            .email-body h3 { color: #2563eb; }
            .email-body p { margin: 0 0 18px 0; }
            .email-body ul, .email-body ol { margin: 0 0 18px 24px; padding: 0; }
            .email-body li { margin-bottom: 10px; }
            .email-body a { color: #7c3aed; text-decoration: none; font-weight: 500; }
            .email-body code { background: #fdf4ff; padding: 3px 8px; border-radius: 6px; font-size: 0.9em; color: #be185d; }
            .email-body pre { background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); color: #e0e7ff; padding: 20px; border-radius: 8px; overflow-x: auto; }
            .email-body pre code { background: none; padding: 0; color: inherit; }
            .email-body blockquote { border-left: 4px solid #f472b6; margin: 20px 0; padding: 16px 24px; background: #fdf2f8; border-radius: 0 8px 8px 0; }
            .email-body table { border-collapse: collapse; width: 100%; margin: 20px 0; }
            .email-body th, .email-body td { border: 2px solid #fce7f3; padding: 14px; text-align: left; }
            .email-body th { background: linear-gradient(135deg, #fce7f3 0%, #fdf2f8 100%); color: #be185d; font-weight: 600; }
            .btn { display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff !important; padding: 14px 36px; border-radius: 30px; text-decoration: none; font-weight: 600; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4); }
            .email-footer { background: linear-gradient(135deg, #fdf4ff 0%, #f0f9ff 100%); padding: 28px 40px; color: #64748b; font-size: 13px; text-align: center; border-top: 2px solid #fce7f3; }
        '''
    }
}


class FragmentLoader(BaseLoader):
    def __init__(self, fragments: Dict[str, str]):
        self.fragments = fragments

    def get_source(self, environment, template):
        if template in self.fragments:
            return self.fragments[template], template, lambda: False
        raise TemplateNotFound(template)


class FragmentInclude(Extension):
    tags = {'fragment'}

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        name = parser.stream.expect('string').value
        return nodes.Output([self.call_method('_include_fragment', [nodes.Const(name)])], lineno=lineno)

    def _include_fragment(self, name):
        return self.environment.fragment_loader.fragments.get(name, f'[片段未找到: {name}]')


def jinja_env(fragments: Dict[str, str]):
    env = Environment(
        loader=BaseLoader(),
        extensions=[FragmentInclude],
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True
    )
    env.fragment_loader = FragmentLoader(fragments)
    return env


def load_json(path: str, default: Any) -> Any:
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default
    return default


def save_json(path: str, data: Any):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@dataclass
class Variable:
    name: str
    type: str
    required: bool
    default: Any = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Variable':
        return cls(**data)


@dataclass
class Template:
    name: str
    subject: str
    body: str
    variables: List[Variable]
    created_at: str
    updated_at: str
    version: int = 1

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['variables'] = [v.to_dict() for v in self.variables]
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> 'Template':
        variables = [Variable.from_dict(v) for v in data.get('variables', [])]
        return cls(
            name=data['name'],
            subject=data['subject'],
            body=data['body'],
            variables=variables,
            created_at=data.get('created_at', datetime.now().isoformat()),
            updated_at=data.get('updated_at', datetime.now().isoformat()),
            version=data.get('version', 1)
        )


@dataclass
class Fragment:
    name: str
    content: str
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Fragment':
        return cls(**data)


def load_templates() -> Dict[str, Template]:
    data = load_json(TEMPLATES_FILE, {})
    return {k: Template.from_dict(v) for k, v in data.items()}


def save_templates(templates: Dict[str, Template]):
    data = {k: v.to_dict() for k, v in templates.items()}
    save_json(TEMPLATES_FILE, data)


def load_fragments() -> Dict[str, Fragment]:
    data = load_json(FRAGMENTS_FILE, {})
    return {k: Fragment.from_dict(v) for k, v in data.items()}


def save_fragments(fragments: Dict[str, Fragment]):
    data = {k: v.to_dict() for k, v in fragments.items()}
    save_json(FRAGMENTS_FILE, data)


def load_stats() -> Dict[str, Dict]:
    return load_json(STATS_FILE, {})


def save_stats(stats: Dict[str, Dict]):
    save_json(STATS_FILE, stats)


def update_stats(template_name: str):
    stats = load_stats()
    now = datetime.now().isoformat()
    if template_name not in stats:
        stats[template_name] = {'use_count': 0, 'last_used': None}
    stats[template_name]['use_count'] += 1
    stats[template_name]['last_used'] = now
    save_stats(stats)


def save_version(template: Template):
    version_dir = os.path.join(VERSIONS_DIR, template.name)
    os.makedirs(version_dir, exist_ok=True)
    version_file = os.path.join(version_dir, f'v{template.version}.json')
    save_json(version_file, template.to_dict())


def load_versions(template_name: str) -> List[int]:
    version_dir = os.path.join(VERSIONS_DIR, template_name)
    if not os.path.exists(version_dir):
        return []
    versions = []
    for f in os.listdir(version_dir):
        if f.startswith('v') and f.endswith('.json'):
            try:
                versions.append(int(f[1:-5]))
            except ValueError:
                pass
    return sorted(versions)


def load_version(template_name: str, version: int) -> Optional[Template]:
    version_file = os.path.join(VERSIONS_DIR, template_name, f'v{version}.json')
    if not os.path.exists(version_file):
        return None
    data = load_json(version_file, None)
    return Template.from_dict(data) if data else None


def validate_variable(value: Any, var_type: str) -> Any:
    if var_type == 'string':
        return str(value)
    elif var_type == 'number':
        try:
            if isinstance(value, (int, float)):
                return value
            if '.' in str(value):
                return float(value)
            return int(value)
        except (ValueError, TypeError):
            raise click.BadParameter(f'值必须是数字类型')
    elif var_type == 'date':
        try:
            datetime.fromisoformat(str(value))
            return value
        except (ValueError, TypeError):
            raise click.BadParameter(f'日期格式必须是 YYYY-MM-DD 或 ISO 格式')
    elif var_type == 'list':
        if isinstance(value, str):
            return [item.strip() for item in value.split(',') if item.strip()]
        if isinstance(value, list):
            return value
        return [str(value)]
    return value


def get_variable_value(var: Variable, provided: Dict[str, Any]) -> Any:
    if var.name in provided:
        val = provided[var.name]
        if val is None or (isinstance(val, str) and val.strip() == ''):
            if not var.required and var.default is not None:
                return var.default
            if var.required:
                raise click.BadParameter(f'缺少必填变量: {var.name}')
            return ''
        return validate_variable(val, var.type)
    if not var.required and var.default is not None:
        return var.default
    if var.required:
        raise click.BadParameter(f'缺少必填变量: {var.name}')
    return ''


def process_fragment_includes(template_body: str, fragments: Dict[str, str]) -> str:
    def replace_include(match):
        name = match.group(1)
        return fragments.get(name, f'[片段未找到: {name}]')

    pattern = r'\{\{>\s*([a-zA-Z_][a-zA-Z0-9_\-]*)\s*\}\}'
    while re.search(pattern, template_body):
        template_body = re.sub(pattern, replace_include, template_body)
    return template_body


def render_template(template: Template, variables: Dict[str, Any], fragments: Dict[str, Fragment]) -> tuple[str, str]:
    frag_content = {k: v.content for k, v in fragments.items()}

    processed_subject = process_fragment_includes(template.subject, frag_content)
    processed_body = process_fragment_includes(template.body, frag_content)

    env = jinja_env(frag_content)

    def to_bool(val):
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes', 'on')
        return bool(val)

    template_vars = {}
    for var in template.variables:
        val = get_variable_value(var, variables)
        if isinstance(val, str) and val.lower() in ('true', 'false', '1', '0', 'yes', 'no', 'on', 'off'):
            template_vars[var.name] = to_bool(val)
        else:
            template_vars[var.name] = val

    try:
        subject_template = env.from_string(processed_subject)
        body_template = env.from_string(processed_body)
        rendered_subject = subject_template.render(**template_vars)
        rendered_body = body_template.render(**template_vars)
    except TemplateSyntaxError as e:
        raise click.BadParameter(f'模板语法错误: {e}')

    return rendered_subject, rendered_body


def markdown_to_text(md_text: str) -> str:
    html = md_lib.markdown(md_text, extensions=['tables', 'fenced_code'])
    soup = BeautifulSoup(html, 'html.parser')

    for br in soup.find_all('br'):
        br.replace_with('\n')
    for p in soup.find_all('p'):
        p.append('\n\n')
    for li in soup.find_all('li'):
        li.insert_before('• ')
        li.append('\n')
    for ul in soup.find_all('ul'):
        ul.append('\n')
    for ol in soup.find_all('ol'):
        for i, li in enumerate(ol.find_all('li'), 1):
            li.string = f'{i}. {li.get_text()}'
        ol.append('\n')
    for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = int(h.name[1])
        prefix = '#' * level + ' '
        h.insert_before(prefix)
        h.append('\n\n')
    for blockquote in soup.find_all('blockquote'):
        for line in blockquote.get_text().strip().split('\n'):
            line.replace_with('> ' + line + '\n')
        blockquote.append('\n')
    for code in soup.find_all('code'):
        if code.parent.name == 'pre':
            continue
        code.insert_before('`')
        code.append('`')
    for pre in soup.find_all('pre'):
        pre.insert_before('\n```\n')
        pre.append('\n```\n')
    for a in soup.find_all('a'):
        href = a.get('href', '')
        text = a.get_text()
        a.replace_with(f'{text} ({href})' if href != text else text)
    for table in soup.find_all('table'):
        rows = []
        for tr in table.find_all('tr'):
            cells = [td.get_text().strip() for td in tr.find_all(['th', 'td'])]
            rows.append(cells)
        if rows:
            table_text = tabulate(rows, headers='firstrow', tablefmt='grid')
            table.replace_with('\n' + table_text + '\n\n')

    text = soup.get_text()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def markdown_to_html_email(md_text: str, subject: str, theme: str = 'business') -> str:
    theme_data = HTML_THEMES.get(theme, HTML_THEMES['business'])

    html_body = md_lib.markdown(
        md_text,
        extensions=['tables', 'fenced_code', 'sane_lists', 'nl2br']
    )

    full_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <title>{subject}</title>
    <style>{theme_data['css']}</style>
</head>
<body>
    <div class="email-container">
        <div class="email-header">
            <h1>{subject}</h1>
        </div>
        <div class="email-body">
            {html_body}
        </div>
        <div class="email-footer">
            本邮件由 MailGen 模板引擎生成 | {{> footer}}
        </div>
    </div>
</body>
</html>'''

    try:
        premailer = Premailer(full_html, remove_classes=False, strip_important=False)
        full_html = premailer.transform()
    except Exception:
        pass

    return full_html


def read_csv_records(csv_path: str) -> List[Dict[str, str]]:
    if not os.path.exists(csv_path):
        raise click.BadParameter(f'CSV 文件不存在: {csv_path}')
    records = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({k.strip(): v.strip() for k, v in row.items() if k})
    return records


def log_send(template_name: str, recipients: List[Dict], output_files: List[str]):
    send_log = load_json(SEND_LOG_FILE, [])
    send_log.append({
        'timestamp': datetime.now().isoformat(),
        'template': template_name,
        'recipient_count': len(recipients),
        'recipients': recipients,
        'output_files': output_files
    })
    save_json(SEND_LOG_FILE, send_log)


def generate_sample_data() -> tuple[Dict[str, Template], Dict[str, Fragment]]:
    fragments = {
        'header': Fragment(
            name='header',
            content='''<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 24px; color: white; border-radius: 8px 8px 0 0;">
    <h2 style="margin: 0; font-size: 20px;">{{ company_name }}</h2>
</div>''',
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        ),
        'footer': Fragment(
            name='footer',
            content='''<div style="padding: 20px; background: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #64748b;">
    <p>© {{ year }} {{ company_name }}. 保留所有权利。</p>
    <p>如有任何问题，请联系 <a href="mailto:support@example.com" style="color: #3b82f6;">support@example.com</a></p>
    <p style="margin-top: 8px; font-size: 11px;">本邮件发送至 {{ recipient_email }}，如果您不想继续收到此类邮件，请<a href="#" style="color: #3b82f6;">退订</a>。</p>
</div>''',
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        ),
        'signature': Fragment(
            name='signature',
            content='''<div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0;">
    <p style="margin: 4px 0;"><strong>{{ sender_name }}</strong></p>
    <p style="margin: 4px 0; color: #64748b;">{{ sender_title }}</p>
    <p style="margin: 4px 0; color: #64748b;">{{ company_name }}</p>
    <p style="margin: 4px 0; font-size: 12px;">📧 {{ sender_email }} | 📱 {{ sender_phone }}</p>
</div>''',
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
    }

    now = datetime.now().isoformat()
    templates = {
        'welcome': Template(
            name='welcome',
            subject='欢迎加入 {{ company_name }}，{{ user_name }}！',
            body='''{{> header}}

# 欢迎加入我们！

亲爱的 {{ user_name }}，

欢迎您加入 **{{ company_name }}**！我们非常高兴您成为我们团队的一员。

## 您的账户信息

- **用户名**: {{ user_name }}
- **邮箱**: {{ recipient_email }}
- **注册日期**: {{ register_date }}

## 下一步操作

1. **完善个人资料** - 登录您的账户，补充个人信息
2. **开始探索** - 浏览我们的功能和服务
3. **获取帮助** - 如有任何问题，请查看帮助中心

{% if has_trial %}
🎁 **新手福利**: 您已获得 {{ trial_days }} 天免费试用期，截止到 {{ trial_end_date }}。
{% endif %}

如果您有任何疑问，随时联系我们的客服团队。

{{> signature}}

{{> footer}}''',
            variables=[
                Variable(name='user_name', type='string', required=True),
                Variable(name='company_name', type='string', required=True),
                Variable(name='recipient_email', type='string', required=True),
                Variable(name='register_date', type='date', required=True),
                Variable(name='has_trial', type='string', required=False, default='false'),
                Variable(name='trial_days', type='number', required=False, default=7),
                Variable(name='trial_end_date', type='date', required=False, default=''),
                Variable(name='sender_name', type='string', required=False, default='客服团队'),
                Variable(name='sender_title', type='string', required=False, default='客户成功经理'),
                Variable(name='sender_email', type='string', required=False, default='welcome@example.com'),
                Variable(name='sender_phone', type='string', required=False, default='400-888-8888'),
                Variable(name='year', type='string', required=False, default='2026')
            ],
            created_at=now,
            updated_at=now,
            version=1
        ),
        'password_reset': Template(
            name='password_reset',
            subject='密码重置请求 - {{ company_name }}',
            body='''{{> header}}

# 密码重置

您好 {{ user_name }}，

我们收到了您的密码重置请求。

## 重置链接

请点击下面的按钮重置您的密码：

<a href="{{ reset_link }}" class="btn">重置密码</a>

或者复制以下链接到浏览器：
`{{ reset_link }}`

**注意**: 此链接将在 {{ expire_hours }} 小时后过期。

{% if not requested_by_user %}
> ⚠️ **安全提示**: 如果您没有发起此请求，请忽略此邮件并联系客服。
{% endif %}

如果您在使用过程中遇到任何问题，请联系我们。

{{> signature}}

{{> footer}}''',
            variables=[
                Variable(name='user_name', type='string', required=True),
                Variable(name='company_name', type='string', required=True),
                Variable(name='recipient_email', type='string', required=True),
                Variable(name='reset_link', type='string', required=True),
                Variable(name='expire_hours', type='number', required=False, default=24),
                Variable(name='requested_by_user', type='string', required=False, default='true'),
                Variable(name='sender_name', type='string', required=False, default='安全团队'),
                Variable(name='sender_title', type='string', required=False, default='安全工程师'),
                Variable(name='sender_email', type='string', required=False, default='security@example.com'),
                Variable(name='sender_phone', type='string', required=False, default='400-888-8888'),
                Variable(name='year', type='string', required=False, default='2026')
            ],
            created_at=now,
            updated_at=now,
            version=1
        ),
        'order_confirmation': Template(
            name='order_confirmation',
            subject='订单确认 #{{ order_id }} - {{ company_name }}',
            body='''{{> header}}

# 订单确认

您好 {{ user_name }}，

感谢您的购买！您的订单已确认。

## 订单信息

| 项目 | 详情 |
|------|------|
| 订单号 | {{ order_id }} |
| 下单时间 | {{ order_date }} |
| 预计送达 | {{ delivery_date }} |
| 支付方式 | {{ payment_method }} |
| 订单金额 | ¥{{ total_amount }} |

## 商品清单

{% for item in order_items %}
- **{{ item.name }}** × {{ item.quantity }} - ¥{{ item.price }}
{% endfor %}

## 收货信息

- **收货人**: {{ shipping_name }}
- **电话**: {{ shipping_phone }}
- **地址**: {{ shipping_address }}

<a href="{{ order_link }}" class="btn">查看订单详情</a>

{% if has_coupon %}
🎊 **下次购物优惠**: 您已获得 ¥{{ coupon_amount }} 优惠券，有效期至 {{ coupon_expire }}。
{% endif %}

如有任何问题，请随时联系我们。

{{> signature}}

{{> footer}}''',
            variables=[
                Variable(name='user_name', type='string', required=True),
                Variable(name='company_name', type='string', required=True),
                Variable(name='recipient_email', type='string', required=True),
                Variable(name='order_id', type='string', required=True),
                Variable(name='order_date', type='date', required=True),
                Variable(name='delivery_date', type='date', required=True),
                Variable(name='payment_method', type='string', required=True),
                Variable(name='total_amount', type='number', required=True),
                Variable(name='order_items', type='list', required=True),
                Variable(name='shipping_name', type='string', required=True),
                Variable(name='shipping_phone', type='string', required=True),
                Variable(name='shipping_address', type='string', required=True),
                Variable(name='order_link', type='string', required=True),
                Variable(name='has_coupon', type='string', required=False, default='false'),
                Variable(name='coupon_amount', type='number', required=False, default=0),
                Variable(name='coupon_expire', type='date', required=False, default=''),
                Variable(name='sender_name', type='string', required=False, default='订单团队'),
                Variable(name='sender_title', type='string', required=False, default='订单管理员'),
                Variable(name='sender_email', type='string', required=False, default='orders@example.com'),
                Variable(name='sender_phone', type='string', required=False, default='400-888-8888'),
                Variable(name='year', type='string', required=False, default='2026')
            ],
            created_at=now,
            updated_at=now,
            version=1
        ),
        'event_invitation': Template(
            name='event_invitation',
            subject='邀请函: {{ event_name }} - 诚邀您参加',
            body='''{{> header}}

# 诚邀您参加

尊敬的 {{ user_name }}，

我们诚挚地邀请您参加 **{{ event_name }}**。

## 活动详情

- **活动主题**: {{ event_name }}
- **活动时间**: {{ event_date }} {{ event_time }}
- **活动地点**: {{ event_location }}
- **活动形式**: {{ event_format }}

## 活动亮点

{% for highlight in event_highlights %}
- {{ highlight }}
{% endfor %}

## 演讲嘉宾

{% for speaker in speakers %}
- **{{ speaker.name }}** - {{ speaker.title }}
{% endfor %}

<a href="{{ rsvp_link }}" class="btn">立即报名</a>

{% if is_vip %}
🌟 **VIP 专享**: 您将享有 VIP 席位、专属休息室及与嘉宾面对面交流的机会。
{% endif %}

名额有限，请尽早报名。如有任何疑问，请联系活动组委会。

期待您的出席！

{{> signature}}

{{> footer}}''',
            variables=[
                Variable(name='user_name', type='string', required=True),
                Variable(name='company_name', type='string', required=True),
                Variable(name='recipient_email', type='string', required=True),
                Variable(name='event_name', type='string', required=True),
                Variable(name='event_date', type='date', required=True),
                Variable(name='event_time', type='string', required=True),
                Variable(name='event_location', type='string', required=True),
                Variable(name='event_format', type='string', required=True),
                Variable(name='event_highlights', type='list', required=True),
                Variable(name='speakers', type='list', required=True),
                Variable(name='rsvp_link', type='string', required=True),
                Variable(name='is_vip', type='string', required=False, default='false'),
                Variable(name='sender_name', type='string', required=False, default='活动组委会'),
                Variable(name='sender_title', type='string', required=False, default='活动负责人'),
                Variable(name='sender_email', type='string', required=False, default='events@example.com'),
                Variable(name='sender_phone', type='string', required=False, default='400-888-8888'),
                Variable(name='year', type='string', required=False, default='2026')
            ],
            created_at=now,
            updated_at=now,
            version=1
        ),
        'weekly_report': Template(
            name='weekly_report',
            subject='周报汇总 - {{ week_range }} {{ company_name }}',
            body='''{{> header}}

# 周报汇总

您好 {{ user_name }}，

以下是 {{ week_range }} 的工作周报。

## 本周工作总结

### 已完成工作

{% for task in completed_tasks %}
- ✅ **{{ task.title }}** - {{ task.description }}
{% endfor %}

### 进行中工作

{% for task in in_progress_tasks %}
- 🔄 **{{ task.title }}** - 进度: {{ task.progress }}%
{% endfor %}

## 关键指标

| 指标 | 本周 | 上周 | 变化 |
|------|------|------|------|
{% for metric in metrics %}
| {{ metric.name }} | {{ metric.current }} | {{ metric.last_week }} | {{ metric.change }} |
{% endfor %}

## 问题与风险

{% if has_issues %}
{% for issue in issues %}
> ⚠️ **{{ issue.title }}**: {{ issue.description }}
{% endfor %}
{% else %}
本周无重大问题。
{% endif %}

## 下周计划

{% for plan in next_week_plans %}
- **{{ plan.title }}** - 负责人: {{ plan.owner }}
{% endfor %}

{% if is_manager %}
📊 **管理者视图**: 您可以点击下方按钮查看完整的团队仪表盘。
<a href="{{ dashboard_link }}" class="btn">查看团队仪表盘</a>
{% endif %}

如有任何疑问，请随时沟通。

{{> signature}}

{{> footer}}''',
            variables=[
                Variable(name='user_name', type='string', required=True),
                Variable(name='company_name', type='string', required=True),
                Variable(name='recipient_email', type='string', required=True),
                Variable(name='week_range', type='string', required=True),
                Variable(name='completed_tasks', type='list', required=True),
                Variable(name='in_progress_tasks', type='list', required=True),
                Variable(name='metrics', type='list', required=True),
                Variable(name='has_issues', type='string', required=False, default='false'),
                Variable(name='issues', type='list', required=False, default=[]),
                Variable(name='next_week_plans', type='list', required=True),
                Variable(name='is_manager', type='string', required=False, default='false'),
                Variable(name='dashboard_link', type='string', required=False, default=''),
                Variable(name='sender_name', type='string', required=False, default='团队负责人'),
                Variable(name='sender_title', type='string', required=False, default='项目经理'),
                Variable(name='sender_email', type='string', required=False, default='report@example.com'),
                Variable(name='sender_phone', type='string', required=False, default='400-888-8888'),
                Variable(name='year', type='string', required=False, default='2026')
            ],
            created_at=now,
            updated_at=now,
            version=1
        )
    }

    return templates, fragments


def init_sample_data():
    templates = load_templates()
    fragments = load_fragments()

    if not templates and not fragments:
        sample_templates, sample_fragments = generate_sample_data()
        save_templates(sample_templates)
        save_fragments(sample_fragments)
        for t in sample_templates.values():
            save_version(t)
        click.echo(Fore.GREEN + '已初始化示例模板和片段。')


def print_error(msg: str):
    click.echo(Fore.RED + '❌ ' + msg)


def print_success(msg: str):
    click.echo(Fore.GREEN + '✅ ' + msg)


def print_info(msg: str):
    click.echo(Fore.CYAN + 'ℹ️ ' + msg)


def print_warning(msg: str):
    click.echo(Fore.YELLOW + '⚠️ ' + msg)


@click.group(help='邮件/通知模板管理与生成工具')
@click.option('--data-dir', default=None, help='数据目录路径')
def cli(data_dir):
    if data_dir:
        global DATA_DIR, TEMPLATES_FILE, FRAGMENTS_FILE, VERSIONS_DIR, SEND_LOG_FILE, STATS_FILE
        DATA_DIR = data_dir
        TEMPLATES_FILE = os.path.join(DATA_DIR, 'templates.json')
        FRAGMENTS_FILE = os.path.join(DATA_DIR, 'fragments.json')
        VERSIONS_DIR = os.path.join(DATA_DIR, 'versions')
        SEND_LOG_FILE = os.path.join(DATA_DIR, 'send_log.json')
        STATS_FILE = os.path.join(DATA_DIR, 'stats.json')
        for d in [DATA_DIR, VERSIONS_DIR]:
            os.makedirs(d, exist_ok=True)
    init_sample_data()


@cli.group(help='模板管理')
def template():
    pass


@template.command('create', help='创建新模板')
@click.option('--name', required=True, help='模板名称')
@click.option('--subject', required=True, help='邮件主题行')
@click.option('--body', required=False, help='邮件正文(Markdown)。不提供则从 --body-file 读取')
@click.option('--body-file', required=False, type=click.File('r', encoding='utf-8'), help='从文件读取正文')
@click.option('--var', 'vars_opt', multiple=True, help='变量定义: 名称:类型:required:默认值。例: user_name:string:true:')
@click.option('--var-file', required=False, type=click.File('r', encoding='utf-8'), help='从JSON文件读取变量定义')
def template_create(name, subject, body, body_file, vars_opt, var_file):
    templates = load_templates()
    if name in templates:
        print_error(f'模板 "{name}" 已存在')
        return

    if body_file:
        body = body_file.read()
    elif not body:
        print_error('必须提供 --body 或 --body-file')
        return

    variables = []
    if var_file:
        var_data = json.load(var_file)
        for v in var_data:
            variables.append(Variable.from_dict(v))
    elif vars_opt:
        for v_def in vars_opt:
            parts = v_def.split(':')
            if len(parts) < 3:
                print_error(f'变量定义格式错误: {v_def}。应为: 名称:类型:required[:默认值]')
                return
            var_name, var_type, required = parts[0], parts[1], parts[2].lower() == 'true'
            default = parts[3] if len(parts) > 3 else None
            if var_type not in ['string', 'number', 'date', 'list']:
                print_error(f'不支持的变量类型: {var_type}。支持: string, number, date, list')
                return
            variables.append(Variable(name=var_name, type=var_type, required=required, default=default))

    now = datetime.now().isoformat()
    template_obj = Template(
        name=name,
        subject=subject,
        body=body,
        variables=variables,
        created_at=now,
        updated_at=now,
        version=1
    )

    templates[name] = template_obj
    save_templates(templates)
    save_version(template_obj)
    print_success(f'模板 "{name}" 创建成功，版本 1')

    if variables:
        click.echo(f'变量列表:')
        for v in variables:
            req = Fore.RED + '必填' if v.required else Fore.YELLOW + '可选'
            click.echo(f'  - {v.name} ({v.type}) {req} 默认: {v.default}')


@template.command('list', help='列出所有模板')
@click.option('--stats', is_flag=True, help='显示使用统计')
def template_list(stats):
    templates = load_templates()
    if not templates:
        print_info('没有模板。')
        return

    stats_data = load_stats() if stats else None
    headers = ['名称', '主题', '变量数', '版本', '创建时间', '更新时间']
    if stats:
        headers += ['使用次数', '最后使用']

    rows = []
    for name, t in sorted(templates.items()):
        row = [
            Fore.CYAN + name + Style.RESET_ALL,
            t.subject[:50] + ('...' if len(t.subject) > 50 else ''),
            len(t.variables),
            t.version,
            t.created_at[:19].replace('T', ' '),
            t.updated_at[:19].replace('T', ' ')
        ]
        if stats and stats_data:
            s = stats_data.get(name, {'use_count': 0, 'last_used': None})
            row += [
                s['use_count'],
                s['last_used'][:19].replace('T', ' ') if s['last_used'] else '-'
            ]
        rows.append(row)

    click.echo(tabulate(rows, headers=headers, tablefmt='pretty'))


@template.command('show', help='查看模板详情')
@click.argument('name')
@click.option('--version', type=int, default=None, help='查看指定版本')
def template_show(name, version):
    templates = load_templates()
    if name not in templates:
        print_error(f'模板 "{name}" 不存在')
        return

    if version:
        t = load_version(name, version)
        if not t:
            print_error(f'版本 {version} 不存在')
            return
    else:
        t = templates[name]

    click.echo(Fore.CYAN + f'=== 模板: {t.name} (版本 {t.version}) ===')
    click.echo(f'{Fore.YELLOW}主题:{Style.RESET_ALL} {t.subject}')
    click.echo(f'{Fore.YELLOW}创建时间:{Style.RESET_ALL} {t.created_at}')
    click.echo(f'{Fore.YELLOW}更新时间:{Style.RESET_ALL} {t.updated_at}')
    click.echo()

    if t.variables:
        click.echo(Fore.YELLOW + '变量定义:')
        for v in t.variables:
            req = Fore.RED + '必填' if v.required else Fore.GREEN + '可选'
            click.echo(f'  {v.name} ({v.type}) {req} - 默认: {v.default}')
        click.echo()

    versions = load_versions(name)
    if versions:
        click.echo(Fore.YELLOW + f'历史版本: {versions}')
        click.echo()

    click.echo(Fore.YELLOW + '正文:')
    click.echo(t.body)


@template.command('edit', help='编辑模板')
@click.option('--name', required=True, help='模板名称')
@click.option('--subject', required=False, help='新的邮件主题行')
@click.option('--body', required=False, help='新的邮件正文')
@click.option('--body-file', required=False, type=click.File('r', encoding='utf-8'), help='从文件读取新的正文')
@click.option('--add-var', multiple=True, help='添加变量: 名称:类型:required:默认值')
@click.option('--remove-var', multiple=True, help='删除变量')
@click.option('--edit-var', multiple=True, help='编辑变量: 名称:类型:required:默认值')
def template_edit(name, subject, body, body_file, add_var, remove_var, edit_var):
    templates = load_templates()
    if name not in templates:
        print_error(f'模板 "{name}" 不存在')
        return

    t = templates[name]
    old_version = t.version

    if subject:
        t.subject = subject

    if body_file:
        t.body = body_file.read()
    elif body:
        t.body = body

    if remove_var:
        for v_name in remove_var:
            t.variables = [v for v in t.variables if v.name != v_name]
            print_info(f'已删除变量: {v_name}')

    if add_var:
        for v_def in add_var:
            parts = v_def.split(':')
            if len(parts) < 3:
                print_error(f'变量定义格式错误: {v_def}')
                return
            var_name, var_type, required = parts[0], parts[1], parts[2].lower() == 'true'
            default = parts[3] if len(parts) > 3 else None
            if any(v.name == var_name for v in t.variables):
                print_error(f'变量已存在: {var_name}')
                return
            t.variables.append(Variable(name=var_name, type=var_type, required=required, default=default))
            print_info(f'已添加变量: {var_name}')

    if edit_var:
        for v_def in edit_var:
            parts = v_def.split(':')
            if len(parts) < 3:
                print_error(f'变量定义格式错误: {v_def}')
                return
            var_name, var_type, required = parts[0], parts[1], parts[2].lower() == 'true'
            default = parts[3] if len(parts) > 3 else None
            found = False
            for i, v in enumerate(t.variables):
                if v.name == var_name:
                    t.variables[i] = Variable(name=var_name, type=var_type, required=required, default=default)
                    found = True
                    print_info(f'已更新变量: {var_name}')
                    break
            if not found:
                print_error(f'变量不存在: {var_name}')
                return

    t.version += 1
    t.updated_at = datetime.now().isoformat()

    save_templates(templates)
    save_version(t)
    print_success(f'模板 "{name}" 已更新，从版本 {old_version} 升级到 {t.version}')


@template.command('delete', help='删除模板')
@click.argument('name')
@click.option('--force', is_flag=True, help='不提示确认')
def template_delete(name, force):
    templates = load_templates()
    if name not in templates:
        print_error(f'模板 "{name}" 不存在')
        return

    if not force:
        if not click.confirm(f'确定要删除模板 "{name}" 吗？此操作不可恢复！'):
            print_info('操作已取消')
            return

    del templates[name]
    save_templates(templates)

    version_dir = os.path.join(VERSIONS_DIR, name)
    if os.path.exists(version_dir):
        shutil.rmtree(version_dir)

    stats = load_stats()
    if name in stats:
        del stats[name]
        save_stats(stats)

    print_success(f'模板 "{name}" 已删除')


@template.command('diff', help='对比两个版本')
@click.argument('name')
@click.argument('version1', type=int)
@click.argument('version2', type=int)
def template_diff(name, version1, version2):
    v1 = load_version(name, version1)
    v2 = load_version(name, version2)
    if not v1:
        print_error(f'版本 {version1} 不存在')
        return
    if not v2:
        print_error(f'版本 {version2} 不存在')
        return

    for field in ['subject', 'body']:
        text1 = getattr(v1, field).splitlines(keepends=True)
        text2 = getattr(v2, field).splitlines(keepends=True)

        if text1 != text2:
            click.echo(Fore.CYAN + f'=== {field} 差异 (v{version1} vs v{version2}) ===')
            diff = difflib.unified_diff(text1, text2, fromfile=f'v{version1}', tofile=f'v{version2}')
            for line in diff:
                if line.startswith('+'):
                    click.echo(Fore.GREEN + line.rstrip())
                elif line.startswith('-'):
                    click.echo(Fore.RED + line.rstrip())
                elif line.startswith('@'):
                    click.echo(Fore.CYAN + line.rstrip())
                else:
                    click.echo(line.rstrip())
            click.echo()


@cli.command('render', help='渲染模板')
@click.option('--template', 'template_name', required=True, help='模板名称')
@click.option('--format', 'output_format', type=click.Choice(['text', 'html']), default='text', help='输出格式')
@click.option('--theme', type=click.Choice(HTML_THEMES.keys()), default='business', help='HTML主题')
@click.option('--var', 'vars_opt', multiple=True, help='变量值: 名称=值')
@click.option('--var-file', required=False, type=click.File('r', encoding='utf-8'), help='从JSON文件读取变量')
@click.option('--csv', required=False, type=click.Path(exists=True), help='从CSV批量读取变量')
@click.option('--output', required=False, type=click.Path(), help='输出文件(批量模式下是目录)')
def render(template_name, output_format, theme, vars_opt, var_file, csv, output):
    templates = load_templates()
    fragments = load_fragments()

    if template_name not in templates:
        print_error(f'模板 "{template_name}" 不存在')
        return

    t = templates[template_name]

    if csv:
        records = read_csv_records(csv)
        update_stats(template_name)

        if output:
            os.makedirs(output, exist_ok=True)

        for i, record in enumerate(records, 1):
            rendered_subject, rendered_body = render_template(t, record, fragments)

            if output_format == 'html':
                content = markdown_to_html_email(rendered_body, rendered_subject, theme)
                ext = '.html'
            else:
                content = f'主题: {rendered_subject}\n\n' + markdown_to_text(rendered_body)
                ext = '.txt'

            if output:
                fname = record.get('recipient_email', f'record_{i}').replace('@', '_at_')
                out_path = os.path.join(output, f'{fname}{ext}')
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print_success(f'已生成: {out_path}')
            else:
                click.echo(f'\n=== 记录 {i} ===')
                click.echo(content)

        print_info(f'批量渲染完成，共 {len(records)} 条记录')
        return

    variables = {}
    if var_file:
        variables = json.load(var_file)
    elif vars_opt:
        for v in vars_opt:
            if '=' in v:
                k, val = v.split('=', 1)
                variables[k.strip()] = val.strip()

    rendered_subject, rendered_body = render_template(t, variables, fragments)
    update_stats(template_name)

    if output_format == 'html':
        content = markdown_to_html_email(rendered_body, rendered_subject, theme)
    else:
        content = f'主题: {rendered_subject}\n\n' + markdown_to_text(rendered_body)

    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(content)
        print_success(f'已渲染到: {output}')
    else:
        click.echo(content)


@cli.command('preview', help='在终端预览渲染效果')
@click.option('--template', 'template_name', required=True, help='模板名称')
@click.option('--var', 'vars_opt', multiple=True, help='变量值: 名称=值')
@click.option('--var-file', required=False, type=click.File('r', encoding='utf-8'), help='从JSON文件读取变量')
def preview(template_name, vars_opt, var_file):
    templates = load_templates()
    fragments = load_fragments()

    if template_name not in templates:
        print_error(f'模板 "{template_name}" 不存在')
        return

    t = templates[template_name]

    variables = {}
    if var_file:
        variables = json.load(var_file)
    elif vars_opt:
        for v in vars_opt:
            if '=' in v:
                k, val = v.split('=', 1)
                variables[k.strip()] = val.strip()

    rendered_subject, rendered_body = render_template(t, variables, fragments)

    terminal_width = min(80, os.get_terminal_size().columns if sys.stdout.isatty() else 80)
    separator = '=' * terminal_width

    click.echo(Fore.CYAN + separator)
    click.echo(Fore.CYAN + '📧 主题: ' + Style.BRIGHT + rendered_subject)
    click.echo(Fore.CYAN + separator)
    click.echo()

    html = md_lib.markdown(rendered_body, extensions=['tables', 'fenced_code'])
    soup = BeautifulSoup(html, 'html.parser')

    for h in soup.find_all(['h1', 'h2', 'h3']):
        h.string = Fore.MAGENTA + Style.BRIGHT + h.get_text() + Style.RESET_ALL
    for strong in soup.find_all('strong'):
        strong.string = Style.BRIGHT + strong.get_text() + Style.RESET_ALL
    for em in soup.find_all('em'):
        em.string = Fore.YELLOW + em.get_text() + Style.RESET_ALL
    for code in soup.find_all('code'):
        if code.parent.name != 'pre':
            code.string = Fore.GREEN + code.get_text() + Style.RESET_ALL
    for pre in soup.find_all('pre'):
        pre.string = Fore.BLACK + Back.WHITE + pre.get_text() + Style.RESET_ALL
    for a in soup.find_all('a'):
        a.string = Fore.BLUE + a.get_text() + Style.RESET_ALL + f' ({a.get("href", "")})'
    for li in soup.find_all('li'):
        li.insert_before('  • ')

    for br in soup.find_all('br'):
        br.replace_with('\n')
    for p in soup.find_all('p'):
        p.append('\n\n')

    text = soup.get_text()
    text = re.sub(r'\n{3,}', '\n\n', text)
    click.echo(text.strip())
    click.echo()
    click.echo(Fore.CYAN + separator)


@cli.command('send', help='模拟批量发送邮件')
@click.option('--template', 'template_name', required=True, help='模板名称')
@click.option('--recipients', required=True, type=click.Path(exists=True), help='收件人CSV文件路径')
@click.option('--theme', type=click.Choice(HTML_THEMES.keys()), default='business', help='HTML主题')
@click.option('--output-dir', default=OUTPUT_DIR, help='输出目录')
def send(template_name, recipients, theme, output_dir):
    templates = load_templates()
    fragments = load_fragments()

    if template_name not in templates:
        print_error(f'模板 "{template_name}" 不存在')
        return

    t = templates[template_name]
    records = read_csv_records(recipients)

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    batch_dir = os.path.join(output_dir, f'{template_name}_{timestamp}')
    os.makedirs(batch_dir, exist_ok=True)

    update_stats(template_name)

    output_files = []
    sent_recipients = []

    for i, record in enumerate(records, 1):
        if 'recipient_email' not in record:
            print_warning(f'记录 {i} 缺少 recipient_email 字段，跳过')
            continue

        email = record['recipient_email']
        try:
            rendered_subject, rendered_body = render_template(t, record, fragments)
            content = markdown_to_html_email(rendered_body, rendered_subject, theme)

            safe_email = email.replace('@', '_at_').replace('.', '_dot_')
            out_path = os.path.join(batch_dir, f'{safe_email}.html')
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(content)

            output_files.append(out_path)
            sent_recipients.append(record)

            click.echo(f'[{i}/{len(records)}] {Fore.GREEN}✓{Style.RESET_ALL} {email} → {out_path}')
        except Exception as e:
            click.echo(f'[{i}/{len(records)}] {Fore.RED}✗{Style.RESET_ALL} {email} - 错误: {e}')

    log_send(template_name, sent_recipients, output_files)

    click.echo()
    print_success(f'发送完成！成功 {len(sent_recipients)}/{len(records)} 封')
    print_info(f'输出目录: {batch_dir}')
    print_info(f'发送日志已记录')


@cli.group(help='片段管理')
def fragment():
    pass


@fragment.command('create', help='创建新片段')
@click.option('--name', required=True, help='片段名称')
@click.option('--content', required=False, help='片段内容')
@click.option('--content-file', required=False, type=click.File('r', encoding='utf-8'), help='从文件读取内容')
def fragment_create(name, content, content_file):
    fragments = load_fragments()
    if name in fragments:
        print_error(f'片段 "{name}" 已存在')
        return

    if content_file:
        content = content_file.read()
    elif not content:
        print_error('必须提供 --content 或 --content-file')
        return

    now = datetime.now().isoformat()
    fragments[name] = Fragment(
        name=name,
        content=content,
        created_at=now,
        updated_at=now
    )
    save_fragments(fragments)
    print_success(f'片段 "{name}" 创建成功')


@fragment.command('list', help='列出所有片段')
def fragment_list():
    fragments = load_fragments()
    if not fragments:
        print_info('没有片段。')
        return

    headers = ['名称', '内容预览', '创建时间', '更新时间']
    rows = []
    for name, f in sorted(fragments.items()):
        preview = f.content.replace('\n', ' ')[:60] + ('...' if len(f.content) > 60 else '')
        rows.append([
            Fore.CYAN + name + Style.RESET_ALL,
            preview,
            f.created_at[:19].replace('T', ' '),
            f.updated_at[:19].replace('T', ' ')
        ])

    click.echo(tabulate(rows, headers=headers, tablefmt='pretty'))


@fragment.command('show', help='查看片段内容')
@click.argument('name')
def fragment_show(name):
    fragments = load_fragments()
    if name not in fragments:
        print_error(f'片段 "{name}" 不存在')
        return

    f = fragments[name]
    click.echo(Fore.CYAN + f'=== 片段: {f.name} ===')
    click.echo(f'{Fore.YELLOW}创建时间:{Style.RESET_ALL} {f.created_at}')
    click.echo(f'{Fore.YELLOW}更新时间:{Style.RESET_ALL} {f.updated_at}')
    click.echo(Fore.YELLOW + '内容:')
    click.echo(f.content)


@fragment.command('edit', help='编辑片段')
@click.option('--name', required=True, help='片段名称')
@click.option('--content', required=False, help='新的内容')
@click.option('--content-file', required=False, type=click.File('r', encoding='utf-8'), help='从文件读取新内容')
def fragment_edit(name, content, content_file):
    fragments = load_fragments()
    if name not in fragments:
        print_error(f'片段 "{name}" 不存在')
        return

    if content_file:
        content = content_file.read()
    elif not content:
        print_error('必须提供 --content 或 --content-file')
        return

    f = fragments[name]
    f.content = content
    f.updated_at = datetime.now().isoformat()
    save_fragments(fragments)
    print_success(f'片段 "{name}" 已更新')


@fragment.command('delete', help='删除片段')
@click.argument('name')
@click.option('--force', is_flag=True, help='不提示确认')
def fragment_delete(name, force):
    fragments = load_fragments()
    if name not in fragments:
        print_error(f'片段 "{name}" 不存在')
        return

    if not force:
        if not click.confirm(f'确定要删除片段 "{name}" 吗？'):
            print_info('操作已取消')
            return

    del fragments[name]
    save_fragments(fragments)
    print_success(f'片段 "{name}" 已删除')


@cli.command('export', help='导出所有模板和片段到ZIP')
@click.option('--output', 'output_path', required=True, type=click.Path(), help='输出ZIP文件路径')
@click.option('--include-versions', is_flag=True, help='包含所有历史版本')
@click.option('--include-stats', is_flag=True, help='包含使用统计')
@click.option('--include-sample-data', is_flag=True, help='包含示例数据CSV')
def export(output_path, include_versions, include_stats, include_sample_data):
    templates = load_templates()
    fragments = load_fragments()

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        export_data = {
            'exported_at': datetime.now().isoformat(),
            'version': '1.0',
            'templates': {k: v.to_dict() for k, v in templates.items()},
            'fragments': {k: v.to_dict() for k, v in fragments.items()}
        }
        zf.writestr('data.json', json.dumps(export_data, ensure_ascii=False, indent=2))

        for name, t in templates.items():
            zf.writestr(f'templates/{name}.json', json.dumps(t.to_dict(), ensure_ascii=False, indent=2))
            zf.writestr(f'templates/{name}_body.md', t.body)

        for name, f in fragments.items():
            zf.writestr(f'fragments/{name}.json', json.dumps(f.to_dict(), ensure_ascii=False, indent=2))
            zf.writestr(f'fragments/{name}_content.md', f.content)

        if include_versions:
            for t_name in templates:
                versions = load_versions(t_name)
                for v in versions:
                    v_obj = load_version(t_name, v)
                    if v_obj:
                        zf.writestr(
                            f'versions/{t_name}/v{v}.json',
                            json.dumps(v_obj.to_dict(), ensure_ascii=False, indent=2)
                        )

        if include_stats:
            stats = load_stats()
            zf.writestr('stats.json', json.dumps(stats, ensure_ascii=False, indent=2))

        if include_sample_data:
            sample_csv = 'recipient_email,user_name,company_name,register_date,has_trial,trial_days\n'
            sample_csv += 'alice@example.com,Alice,科技公司,2026-06-01,true,14\n'
            sample_csv += 'bob@example.com,Bob,科技公司,2026-06-05,false,7\n'
            zf.writestr('sample_data/recipients_welcome.csv', sample_csv)

            sample_vars = {
                "user_name": "测试用户",
                "company_name": "示例公司",
                "recipient_email": "test@example.com",
                "register_date": "2026-06-08"
            }
            zf.writestr('sample_data/vars_welcome.json', json.dumps(sample_vars, ensure_ascii=False, indent=2))

    print_success(f'已导出到: {output_path}')


@cli.command('import', help='从ZIP导入模板和片段')
@click.option('--input', 'input_path', required=True, type=click.Path(exists=True), help='ZIP文件路径')
@click.option('--overwrite', is_flag=True, help='覆盖已存在的模板/片段')
@click.option('--dry-run', is_flag=True, help='只预览导入内容，不实际导入')
def import_cmd(input_path, overwrite, dry_run):
    with zipfile.ZipFile(input_path, 'r') as zf:
        if 'data.json' not in zf.namelist():
            print_error('ZIP文件格式错误: 缺少 data.json')
            return

        data = json.loads(zf.read('data.json').decode('utf-8'))
        templates_data = data.get('templates', {})
        fragments_data = data.get('fragments', {})

        existing_templates = load_templates()
        existing_fragments = load_fragments()

        to_import_templates = {}
        to_import_fragments = {}
        conflicts = []

        for name, t_data in templates_data.items():
            if name in existing_templates and not overwrite:
                conflicts.append(f'模板: {name} (已存在)')
            else:
                to_import_templates[name] = Template.from_dict(t_data)

        for name, f_data in fragments_data.items():
            if name in existing_fragments and not overwrite:
                conflicts.append(f'片段: {name} (已存在)')
            else:
                to_import_fragments[name] = Fragment.from_dict(f_data)

        click.echo(Fore.CYAN + '=== 导入预览 ===')
        click.echo(f'模板: {len(to_import_templates)} 个')
        for name in to_import_templates:
            action = Fore.YELLOW + '覆盖' if name in existing_templates else Fore.GREEN + '新增'
            click.echo(f'  {action} {name}')

        click.echo(f'片段: {len(to_import_fragments)} 个')
        for name in to_import_fragments:
            action = Fore.YELLOW + '覆盖' if name in existing_fragments else Fore.GREEN + '新增'
            click.echo(f'  {action} {name}')

        if conflicts:
            click.echo()
            print_warning(f'冲突项 ({len(conflicts)} 个，使用 --overwrite 覆盖):')
            for c in conflicts:
                click.echo(f'  {c}')

        if dry_run:
            print_info('预览模式，未实际导入。')
            return

        if conflicts and not overwrite:
            print_error('存在冲突，取消导入。使用 --overwrite 覆盖已有内容。')
            return

        for name, t in to_import_templates.items():
            existing_templates[name] = t
            save_version(t)

        for name, f in to_import_fragments.items():
            existing_fragments[name] = f

        save_templates(existing_templates)
        save_fragments(existing_fragments)

        print_success(f'导入完成: {len(to_import_templates)} 个模板, {len(to_import_fragments)} 个片段')


@cli.command('stats', help='显示使用统计')
@click.option('--template', 'template_name', required=False, help='指定模板名称')
@click.option('--send-log', is_flag=True, help='显示发送日志')
def stats_cmd(template_name, send_log):
    stats = load_stats()

    if send_log:
        send_log_data = load_json(SEND_LOG_FILE, [])
        if not send_log_data:
            print_info('没有发送记录。')
            return

        headers = ['时间', '模板', '收件人数']
        rows = []
        for entry in reversed(send_log_data[-20:]):
            rows.append([
                entry['timestamp'][:19].replace('T', ' '),
                entry['template'],
                entry['recipient_count']
            ])
        click.echo(tabulate(rows, headers=headers, tablefmt='pretty'))
        return

    templates = load_templates()

    if template_name:
        if template_name not in templates:
            print_error(f'模板 "{template_name}" 不存在')
            return
        s = stats.get(template_name, {'use_count': 0, 'last_used': None})
        click.echo(Fore.CYAN + f'=== 模板: {template_name} ===')
        click.echo(f'使用次数: {s["use_count"]}')
        click.echo(f'最后使用: {s["last_used"] if s["last_used"] else "从未使用"}')
        return

    headers = ['模板', '使用次数', '最后使用', '版本', '变量数']
    rows = []
    for name, t in sorted(templates.items()):
        s = stats.get(name, {'use_count': 0, 'last_used': None})
        rows.append([
            Fore.CYAN + name + Style.RESET_ALL,
            s['use_count'],
            s['last_used'][:19].replace('T', ' ') if s['last_used'] else '-',
            t.version,
            len(t.variables)
        ])

    click.echo(tabulate(rows, headers=headers, tablefmt='pretty'))

    total_uses = sum(s['use_count'] for s in stats.values())
    click.echo()
    click.echo(f'总模板数: {len(templates)} | 总片段数: {len(load_fragments())} | 总使用次数: {total_uses}')


if __name__ == '__main__':
    cli()
