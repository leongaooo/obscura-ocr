const form = document.querySelector('#upload');
const status = document.querySelector('#status');
const submit = document.querySelector('#submit');
const download = document.querySelector('#download');
const fields = document.querySelector('#fields');
let result = null;

async function readiness() {
  try {
    const response = await fetch('/health/ready', { cache: 'no-store' });
    status.textContent = response.ok ? '真实 OCR 引擎已就绪 / Ready' : '引擎尚未就绪，请检查模型配置。';
  } catch {
    status.textContent = '无法连接当前服务，请检查服务是否正在运行。';
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  submit.disabled = true;
  download.disabled = true;
  fields.replaceChildren();
  result = null;
  document.querySelector('#json').textContent = '识别中…';
  document.querySelector('#summary').textContent = '正在提取文字与字段证据。';
  status.textContent = '识别中，请稍候；首次推理可能需要较长时间。';
  try {
    const response = await fetch('/api/recognize', { method: 'POST', body: new FormData(form) });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.message || (response.status === 422 ? '请选择符合要求的文件。' : '服务未返回业务消息。'));
    }
    result = body;
    document.querySelector('#summary').textContent = `${body.tokens.length} 个文字块 · ${body.durationMs} ms · ${body.documentType}`;
    for (const [name, candidate] of Object.entries(body.candidates)) {
      if (candidate.value === null) continue;
      const label = document.createElement('dt');
      const value = document.createElement('dd');
      label.textContent = name;
      value.textContent = typeof candidate.value === 'object' ? JSON.stringify(candidate.value) : candidate.value;
      fields.append(label, value);
    }
    document.querySelector('#json').textContent = JSON.stringify(body, null, 2);
    status.textContent = '识别完成，请人工确认字段。';
    download.disabled = false;
  } catch (error) {
    status.textContent = error.message;
    document.querySelector('#json').textContent = '本次没有可用结果。';
    document.querySelector('#summary').textContent = '请调整文件后重试。';
  } finally {
    submit.disabled = false;
  }
});

download.addEventListener('click', () => {
  if (!result) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'obscura-result.json';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

readiness();
