from fastapi import FastAPI
from fastapi import UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import config
from src import llm_extract
from utils import format, document

app = FastAPI()
app_config = config.get_app_config()

# Add the CORS middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config['cors_allow_origins'],
    allow_methods=['*'],
    allow_headers=['*'],
    allow_credentials=True,
)


async def analysis_v2(file_bytes):
    resume_text = await document.get_resume_text(file_bytes)
    form_data = llm_extract.extract_resume_by_llm(resume_text)
    return form_data


@app.post('/analysis')
async def request(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        form_data = await analysis_v2(file_content)
        output_dict = format.convert_keys_to_camel_case(form_data)
        return {"status": "success", "form_data": output_dict}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn

    uvicorn.run("script:app", host=app_config['host'], port=app_config['port'])
