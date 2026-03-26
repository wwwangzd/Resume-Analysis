from fastapi import FastAPI
from fastapi import UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import config
from config.logger import configure_logging, get_logger, log_stage_timing, start_timer
from src import llm_extract
from utils import format, document

configure_logging()

app = FastAPI()
app_config = config.get_app_config()
logger = get_logger('resume_analysis.api')

# Add the CORS middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config['cors_allow_origins'],
    allow_methods=['*'],
    allow_headers=['*'],
    allow_credentials=True,
)


async def analysis_v2(file_bytes):
    analysis_start = start_timer()
    resume_text = await document.get_resume_text(file_bytes)
    log_stage_timing(logger, 'document_stage', analysis_start, text_length=len(resume_text))

    llm_start = start_timer()
    form_data = llm_extract.extract_resume_by_llm(resume_text)
    log_stage_timing(logger, 'llm_stage', llm_start, text_length=len(resume_text))
    log_stage_timing(logger, 'analysis_total', analysis_start, text_length=len(resume_text))
    return form_data


@app.post('/analysis')
async def request(file: UploadFile = File(...)):
    request_start = start_timer()
    try:
        logger.info('Resume analysis request started filename=%s', file.filename)

        read_start = start_timer()
        file_content = await file.read()
        log_stage_timing(logger, 'request_file_read', read_start, file_size_bytes=len(file_content))

        form_data = await analysis_v2(file_content)

        format_start = start_timer()
        output_dict = format.convert_keys_to_camel_case(form_data)
        log_stage_timing(logger, 'response_format', format_start, top_level_keys=len(output_dict))
        log_stage_timing(logger, 'request_total', request_start, filename=file.filename, success=True)
        return {"status": "success", "form_data": output_dict}
    except Exception as e:
        log_stage_timing(logger, 'request_total', request_start, filename=file.filename, success=False)
        logger.exception('Resume analysis request failed filename=%s', file.filename)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn

    uvicorn.run("src.script:app", host=app_config['host'], port=app_config['port'])
