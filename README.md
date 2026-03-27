# Resume-Analysis

## 中文

简历解析服务，基于 FastAPI、PDF 原生文本提取、PaddleOCR 和 LLM，对 PDF 简历进行结构化抽取。

### 功能

- 支持 PDF 简历解析。
- 优先使用 PDF 原生文本提取，文本不足时自动回退到 OCR。
- 基于 LLM 输出结构化结果。
- 固定输出六个模块：基础信息、实习/工作经历、项目经历、获奖信息、自我评价、其他。
- 提供 `POST /analysis` 接口，返回 camelCase 风格字段。

### 运行要求

- Python 3.10+
- 需要可用的 DashScope / 通义调用凭证，例如环境变量 `DASHSCOPE_API_KEY`

### 本地运行

```bash
pip install -r requirements.txt
export DASHSCOPE_API_KEY=your_api_key
python src/script.py
```

服务默认监听 `http://127.0.0.1:8999`。

### Docker 运行

```bash
docker build -t resume-analysis .
docker run -p 8999:8999 -e DASHSCOPE_API_KEY=your_api_key resume-analysis
```

### 接口示例

```bash
curl -X POST "http://127.0.0.1:8999/analysis" \
  -F "file=@/path/to/resume.pdf"
```

### 配置

- 主要配置文件：`config/settings.json`
- 可配置项包括服务端口、LLM 提示词与输出结构、OCR 参数、文本预处理和日志

### 许可证

本项目使用 MIT License。

---

## English

Resume parsing service built with FastAPI, native PDF text extraction, PaddleOCR, and an LLM to extract structured information from PDF resumes.

### Features

- Supports PDF resume parsing.
- Uses native PDF text extraction first and falls back to OCR when needed.
- Produces structured output with an LLM.
- Returns six fixed sections: basic information, internship/work experience, project experience, awards, self-evaluation, and others.
- Exposes a `POST /analysis` API and returns camelCase fields.

### Requirements

- Python 3.10+
- A valid DashScope / Tongyi credential, for example `DASHSCOPE_API_KEY`

### Run Locally

```bash
pip install -r requirements.txt
export DASHSCOPE_API_KEY=your_api_key
python src/script.py
```

The service listens on `http://127.0.0.1:8999` by default.

### Run with Docker

```bash
docker build -t resume-analysis .
docker run -p 8999:8999 -e DASHSCOPE_API_KEY=your_api_key resume-analysis
```

### API Example

```bash
curl -X POST "http://127.0.0.1:8999/analysis" \
  -F "file=@/path/to/resume.pdf"
```

### Configuration

- Main config file: `config/settings.json`
- Configurable items include server port, LLM prompt and schema, OCR parameters, text preprocessing, and logging

### License

This project is licensed under the MIT License.
