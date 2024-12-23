from langfuse.decorators import observe
from utils.log_utils import get_logger
from .generator import Generator
import asyncio
from schemas.api_response_schema import ChatLogicInputData
from source.config.env_config import OVERLOAD_MESSAGE
from pydantic import BaseModel, Field, field_validator



class QuestionAnalysis(BaseModel):
   """Model for analyzing user questions based on complexity and Getfly relevance"""
   analysis: str = Field(description="Đây là nơi bạn viết các phân tích dùng để phục vụ cho câu trả lời")
   
   customer_service_request: bool = Field(
      default=None,
      description="Xác định xem người dùng có yêu cầu kết nối đến bộ phận chăm sóc khách hàng hay không?"
   )
   complexity_score: int = Field(
      description="Chấm điểm cho độ phức tạp của đầu vào từ 1-10, trong đó 1 là rất đơn giản và 10 là rất phức tạp",
      ge=1,  # greater than or equal to 1
      le=10  # less than or equal to 10
   )
   is_vpbank_relevant: int = Field(
      description="Chấm điểm cho độ liên quan của đầu vào đến VPBank từ 1-10, trong đó 1 là không liên quan và 10 là rất liên quan",
      ge=1,  # greater than or equal to 1
      le=10  # less than or equal to 10
   )
   is_social_conversation: bool = Field(
      description="Xác định xem đầu vào của người dùng có phải là đối thoại xã giao (chào hỏi, cảm ơn, xin lỗi, tạm biệt) hay không?"
   )


   @field_validator('analysis')  # Sửa tên trường ở đây
   @classmethod
   def validate_analysis(cls, v):
      if not v.strip():
            raise ValueError('Phân tích không được để trống')
      return v

   @field_validator('customer_service_request')
   def check_customer_service_request(cls, v):
      if v is None:
         raise ValueError('Đánh giá tính rõ ràng của đầu vào không được để trống.')
      return v


   @field_validator('complexity_score')
   @classmethod
   def validate_complexity_score(cls, v) -> int:
      if not (1 <= v <= 10):
            raise ValueError('Complexity score must be between 1 and 5')
      return v
   
   @field_validator('is_vpbank_relevant')
   @classmethod
   def validate_is_vpbank_relevant(cls, v) -> int:
      if not (1 <= v <= 10):
         raise ValueError('Điểm liên quan đến VPBank phải nằm trong khoảng từ 1 đến 10')
      return v
   
   @field_validator('is_social_conversation')
   @classmethod
   def validate_is_social_conversation(cls, v) -> bool:
      return v


logger = get_logger(__name__)
system_prompt = """\
# THÔNG TIN VỀ VPBank
Ngân hàng Thương mại cổ phần Việt Nam Thịnh Vượng (VPBank) được thành lập ngày 12 tháng 8 năm 1993, là một trong những ngân hàng thương mại cổ phần có lịch sử lâu đời ở Việt Nam. Sau gần 31 năm hoạt động, VPBank đã phát triển mạng lưới lên 233 chi nhánh/phòng giao dịch với đội ngũ gần 25.000 cán bộ nhân viên tại thời điểm ngày 30 tháng 6 năm 2021. Hết năm 2020, tổng thu nhập hoạt động của VPBank đạt 39.000 tỷ đồng. Lợi nhuận trước thuế của VPBank năm 2020 đạt mức 13.019 tỷ đồng, hoàn thành 127,5% kế hoạch và tăng 26,1% so với năm 2019, xếp thứ 4 trong các ngân hàng tại Việt Nam. Năm 2023 VPBank đặt lợi nhuận đạt 24.000 tỉ đồng

# NHIỆM VỤ
Suy nghĩ thật kĩ và thực hiện phân tích đầu vào của người dùng theo từng bước dưới đây:
   1. Nhận diện xem người dùng có yêu cầu kết nối đến bộ phậm chăm sóc khách hàng hay không
   2. Độ phức tạp:
      - Đánh giá độ phức tạp của đầu vào của người dùng dựa vào
         - Theo thang điểm từ 1 đến 10, trong đó 1 là rất đơn giản và 10 là rất phức tạp
         - Độ dài: đầu vào càng dài thì điểm càng cao, càng ngắn thì điểm càng thấp
         - Các mệnh đề và ý định có trong đầu vào: càng nhiều thì điểm càng cao, càng ngắn thì điểm càng thấp
   3. Mối liên quan với VPBank:
      - Đánh giá dựa trên thang điểm từ 1 đến 10, trong đó 1 là không liên quan và 10 là rất liên quan
   4. Đối thoại xã giao, thường lệ:
      - Xác định xem đầu vào của người dùng có phải một câu chào hỏi, cảm ơn, xin lỗi, tạm biệt,... hay không

# LỊCH SỬ TRÒ CHUYỆN
```
{chat_history}
```
      
# ĐẦU VÀO CỦA NGƯỜI DÙNG
```
{question}
```
"""


class RoutingQuestion:
   def __init__(
      self,
      generator: Generator,
      max_retries: int = 20,
      retry_delay: float = 2.0
   ) -> None:
      self.generator = generator
      self.max_retries = max_retries
      self.retry_delay = retry_delay

   @observe(name="RoutingQuestion")
   async def run(self, user_data: ChatLogicInputData, question: str) -> str:
      if len(user_data.histories) < 5:
         taken_messages = user_data.histories  # Lấy tất cả nếu ít hơn 5
      else:
         taken_messages = user_data.histories[-5:-1]

      chat_history: str = "\n".join(map(lambda message: f"{message.role}: {message.content}", taken_messages))
      
      for attempt in range(self.max_retries):
         try:
            response = await self.generator.run(
                     prompt = system_prompt.format(
                        question=question,
                        chat_history=chat_history,
                        ),
                     temperature = 0.2,
                     response_model=QuestionAnalysis,
            )
            result = {
               "analysis": response.analysis,
               "customer_service_request": response.customer_service_request,
               "complexity_score": response.complexity_score,
               "is_vpbank_relevant": response.is_vpbank_relevant,
               "is_social_conversation": response.is_social_conversation
            }

            return result
         
         
         except Exception as e:
            if attempt < self.max_retries - 1:
               logger.warning(f"Lỗi khi gọi Enrichment (lần thử {attempt + 1}/{self.max_retries}): {str(e)}")
               await asyncio.sleep(self.retry_delay * (2 ** attempt))
            else:
               logger.error("Đã hết số lần thử lại. Không thể tăng cường.")
               return OVERLOAD_MESSAGE