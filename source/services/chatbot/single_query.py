from .__init__ import *
from langfuse.decorators import observe
from utils.log_utils import get_logger
from schemas.api_response_schema import ChatLogicInputData
from .generator import Generator
from datetime import datetime
import pytz
import asyncio
from source.config.env_config import OVERLOAD_MESSAGE
from pydantic import BaseModel, Field, field_validator
import traceback

# Đặt múi giờ thành múi giờ Việt Nam
timezone = pytz.timezone('Asia/Ho_Chi_Minh')

class RewritePrompt(BaseModel):
   analysis: str = Field(description="Phân tích bối cảnh trò chuyện")
   rewrited_prompt: str = Field(description="Đầu vào của người dùng được viết lại để truy xuất các tài liệu liên quan từ cơ sở dữ liệu vector")

   @field_validator('analysis')  # Sửa tên trường ở đây
   @classmethod
   def validate_analysis(cls, v):
      if not v.strip():
            raise ValueError('Phân tích không được để trống')
      return v
   

   @field_validator('rewrited_prompt')  # Sửa tên trường ở đây
   @classmethod
   def validate_rewrited_prompt(cls, v):
      if not v.strip():
            raise ValueError('Nội dung prompt không được để trống')
      return v


logger = get_logger(__name__)
system_prompt = """\
# NGÀY VÀ GIỜ
Ngày và giờ hiện tại là {current_time}.

# VAI TRÒ
Bạn là VPBank Pro, trợ lý chuyên nghiệp của VPBank - Ngân hàng Thương mại cổ phần Việt Nam Thịnh Vượng

# THÔNG TIN VỀ VPBank
Ngân hàng Thương mại cổ phần Việt Nam Thịnh Vượng (VPBank) được thành lập ngày 12 tháng 8 năm 1993, là một trong những ngân hàng thương mại cổ phần có lịch sử lâu đời ở Việt Nam. Sau gần 31 năm hoạt động, VPBank đã phát triển mạng lưới lên 233 chi nhánh/phòng giao dịch với đội ngũ gần 25.000 cán bộ nhân viên tại thời điểm ngày 30 tháng 6 năm 2021. Hết năm 2020, tổng thu nhập hoạt động của VPBank đạt 39.000 tỷ đồng. Lợi nhuận trước thuế của VPBank năm 2020 đạt mức 13.019 tỷ đồng, hoàn thành 127,5% kế hoạch và tăng 26,1% so với năm 2019, xếp thứ 4 trong các ngân hàng tại Việt Nam. Năm 2023 VPBank đặt lợi nhuận đạt 24.000 tỉ đồng

# NHIỆM VỤ
Phân tích và viết lại đầu vào của người dùng thành một prompt độc lập để truy xuất tài liệu từ cơ sở dữ liệu vector

## QUY TRÌNH THỰC HIỆN
Suy nghĩ từng bước và thực hiện theo từng bước dưới đây:
1. Phân tích bối cảnh trò chuyện:
   - Thứ tự ưu tiên: Đầu vào của người dùng > Lịch sử trò chuyện > Tóm tắt lịch sử trò chuyện
   - Đánh giá từ nhiều góc độ
   - Xác định các thực thể, mệnh đề, các mối quan hệ, và ý định chính
   - Loại bỏ thông tin dư thừa, tập trung vào nội dung chính và ý định của người dùng
2. Viết lại prompt độc lập
   - Hạn chế sử dụng ngữ cảnh trước đó nếu không cần thiết
   - Sử dụng ngôn ngữ đầu vào của người dùng
   - Không sử dụng chủ ngữ, vị ngữ
   - Tập trung vào nội dung chính và ý định của người dùng

# BỐI CẢNH TRÒ CHUYỆN:
Tóm tắt lịch sử trò chuyện:
```
<summary history>
{summary_history}
</summary_history>
```

Lịch sử trò chuyện:
```
<chat history>
{chat_history}
</chat history>
```

Đầu vào của người dùng:
```
<user's input>
{question}
</user's input>
```
"""




class SingleQuery:
   def __init__(
      self,
      generator: Generator,
      max_retries: int = 20,
      retry_delay: float = 2.0
   ) -> None:
      self.generator = generator
      self.max_retries = max_retries
      self.retry_delay = retry_delay

   @observe(name="SingleQuery")
   async def run(self, user_data: ChatLogicInputData, question: str) -> str:
      if len(user_data.histories) < 5:
         taken_messages = user_data.histories  # Lấy tất cả nếu ít hơn 5
      else:
         taken_messages = user_data.histories[-5:-1]

      # Giả sử taken_messages là danh sách các tin nhắn trong chat history
      chat_history: str = "\n".join(map(lambda message: f"{message.role}: {message.content}", taken_messages))
      current_time = datetime.now(timezone).strftime("%A, %Y-%m-%d %H:%M:%S")
      summary_history: str = user_data.summary


      for attempt in range(self.max_retries):
         try:
            response = await self.generator.run(
                     prompt = system_prompt.format(
                        current_time=current_time,
                        summary_history=summary_history,
                        chat_history=chat_history, 
                        question=question,
                        ),
                     temperature = 0.2,
                     response_model=RewritePrompt,
            )
            result = {
               "analysis": response.analysis,
               "rewrite_prompt": response.rewrited_prompt,
            }
            return result

         except Exception as e:
            logger.warning(f"Lỗi khi gọi Enrichment (lần thử {attempt + 1}/{self.max_retries}): {str(e)}")
            logger.error(traceback.format_exc())
            if attempt < self.max_retries - 1:
               await asyncio.sleep(self.retry_delay * (2 ** attempt))
            else:
               logger.error("Đã hết số lần thử lại. Không thể tăng cường.")
               return OVERLOAD_MESSAGE