from langfuse.decorators import observe
from utils.log_utils import get_logger
from .generator import Generator
import asyncio
from schemas.api_response_schema import ChatLogicInputData
from source.config.env_config import OVERLOAD_MESSAGE
from pydantic import BaseModel, Field, field_validator

logger = get_logger(__name__)
system_prompt = """\
Bạn là trợ lý của VPBank, nhiệm vụ của bạn là tham gia vào các cuộc trò chuyện lịch sự và thân thiện với khách hàng. Vui lòng trả lời phù hợp với các tương tác xã giao thông thường như chào hỏi, cảm ơn, xin lỗi và tạm biệt.
      
# ĐẦU VÀO CỦA NGƯỜI DÙNG
```
{question}
```
"""


class ChitChat:
   def __init__(
      self,
      generator: Generator,
      max_retries: int = 20,
      retry_delay: float = 2.0
   ) -> None:
      self.generator = generator
      self.max_retries = max_retries
      self.retry_delay = retry_delay

   @observe(name="ChitChat")
   async def run(self, question: str) -> str:
      for attempt in range(self.max_retries):
         try:
            response = await self.generator.run(
                     prompt = system_prompt.format(
                        question=question
                        ),
                     temperature = 0.2,
            )
            
            return response.strip()
         
         
         except Exception as e:
            if attempt < self.max_retries - 1:
               logger.warning(f"Lỗi khi gọi Enrichment (lần thử {attempt + 1}/{self.max_retries}): {str(e)}")
               await asyncio.sleep(self.retry_delay * (2 ** attempt))
            else:
               logger.error("Đã hết số lần thử lại. Không thể tăng cường.")
               return OVERLOAD_MESSAGE