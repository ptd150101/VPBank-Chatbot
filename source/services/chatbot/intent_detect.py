from langfuse.decorators import observe
from utils.log_utils import get_logger
from .generator import Generator
import asyncio
from source.config.env_config import OVERLOAD_MESSAGE
from pydantic import BaseModel, Field, field_validator



class IntentAnalysis(BaseModel):
    """Model for analyzing user questions based on complexity and Getfly relevance"""
    intent_analysis: str = Field(description="Đây là nơi bạn viết các phân tích dùng để phục vụ cho câu trả lời")
    is_query_answerable: bool = Field(default=False, description="Có đủ dữ kiện để trả lời hay không?")
    intent_id: int = Field(description="ID của intent mà bạn nhận diện")


logger = get_logger(__name__)
system_prompt = """\
# NHIỆM VỤ
Suy nghĩ thật kĩ và thực hiện từng bước theo flow Mermaid dưới đây:
    A[Bắt đầu] --> B[Phân tích đầu vào của người dùng, từ đó nhận diện xem người dùng có muốn thanh toán cước điện thoại hay không?]
    B -->|Có| C[Trả về intent_id = 1]
    B -->|Không| D[Phân tích đầu vào của người dùng, từ đó nhận diện xem người dùng có muốn khóa thẻ credit card hay không?]
    D -->|Có| E[Trả về intent_id = 2]
    D -->|Không| F[Phân tích đầu vào của người dùng, từ đó nhận diện xem người dùng có muốn thống kê tiền vào tiền ra trong vòng 1 tháng trở lại đây hay không?]
    F -->|Có| G[Trả về intent_id = 3]
    F -->|Không| H[Phân tích đầu vào của người dùng, từ đó nhận diện xem người dùng có muốn nạp tiền điện thoại hay không?]
    H -->|Có| I[Trả về intent_id = 4]
    H -->|Không| J[Trả về intent_id = 5]

Nếu không đủ dữ kiện để trả lời, thì cũng trả về intent_id là 5

# ĐẦU VÀO CỦA NGƯỜI DÙNG
```
{question}
```
"""


class IntentDetect:
    def __init__(
        self,
        generator: Generator,
        max_retries: int = 20,
        retry_delay: float = 2.0
    ) -> None:
        self.generator = generator
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    @observe(name="IntentDetect")
    async def run(self, question: str) -> str:
        for attempt in range(self.max_retries):
            try:
                response = await self.generator.run(
                        prompt = system_prompt.format(
                            question=question,
                            ),
                        temperature = 0.2,
                        response_model=IntentAnalysis,
                )
                result = {
                "intent_analysis": response.intent_analysis,
                "intent_id": response.intent_id,
            }

                return result
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Lỗi khi gọi Enrichment (lần thử {attempt + 1}/{self.max_retries}): {str(e)}")
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    logger.error("Đã hết số lần thử lại. Không thể tăng cường.")
                    return OVERLOAD_MESSAGE