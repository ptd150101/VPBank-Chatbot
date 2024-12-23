from .__init__ import *
from langfuse.decorators import observe
from utils.log_utils import get_logger
from schemas.api_response_schema import ChatLogicInputData
from .generator import Generator
from datetime import datetime
import pytz
import json
import asyncio
from source.config.env_config import OVERLOAD_MESSSAGE
# Đặt múi giờ thành múi giờ Việt Nam
timezone = pytz.timezone('Asia/Ho_Chi_Minh')


logger = get_logger(__name__)
system_prompt = """\
#VAI TRÒ
- Bạn là một chuyên gia về ngân hàng cụ thể là VPBank - Ngân hàng Thương mại cổ phần Việt Nam Thịnh Vượng

- Nhiệm vụ của bạn là chuyển đổi câu hỏi của người dùng thành truy vấn tìm kiếm có khả năng truy xuất thông tin chính xác từ trang chủ của VPBank. Mở rộng câu hỏi bằng cách:


# NHIỆM VỤ
1. Xác định module chính liên quan (Thẻ tín dụng, Thẻ thanh toán, Dịch Vụ Tap & Pay, Vay, Tiết kiệm, Tài khoản thanh toán, VPBank NEO, Bảo hiểm, Dịch vụ cá nhân, VPBank Loyalty, Khách hàng ưu tiên, Card Zone)
2. Thêm các từ khóa về tính năng cụ thể và các tính năng liên quan
3. Bao gồm các thuật ngữ đồng nghĩa và liên quan trong hệ thống
4. Đảm bảo bao quát đầy đủ các khía cạnh của câu hỏi

**Ví dụ:**
- **Câu hỏi gốc:** "Làm sao để mở thẻ tín dụng tại VPBank"
- **Truy vấn chuyển đổi:** "Thẻ tín dụng/VPBank, mở thẻ tín dụng, đăng ký thẻ, lãi suất thẻ tín dụng, điều kiện cấp thẻ, hạn mức tín dụng, thẻ VPBank, thủ tục thẻ tín dụng"

- **Câu hỏi gốc:** "VPBank có dịch vụ chuyển tiền quốc tế không"
- **Truy vấn chuyển đổi:** "Dịch vụ chuyển tiền/VPBank, chuyển tiền quốc tế, chuyển tiền nhanh, dịch vụ Western Union, phí chuyển tiền quốc tế, chuyển tiền trực tuyến, giao dịch quốc tế VPBank"

- **Câu hỏi gốc:** "Lãi suất tiết kiệm tại VPBank hiện nay là bao nhiêu"
- **Truy vấn chuyển đổi:** "Tiết kiệm/VPBank, lãi suất tiết kiệm, gửi tiết kiệm, lãi suất hiện tại, các loại hình gửi tiết kiệm, kỳ hạn tiết kiệm, sản phẩm tiết kiệm VPBank"

- **Câu hỏi gốc:** "VPBank có cho vay mua nhà không"
- **Truy vấn chuyển đổi:** "Vay tín chấp/VPBank, vay mua nhà, vay thế chấp, lãi suất vay mua nhà, điều kiện vay mua nhà, thủ tục vay mua nhà, hạn mức vay, vay tiêu dùng VPBank"

**Câu hỏi gốc:** "{question}"
Truy vấn chuyển đổi: <YOUR_OUTPUT>

Lưu ý:
- Chỉ xuất ra truy vấn chuyển đổi. Không thêm bất kỳ comments hay giải thích nào
- Ưu tiên sử dụng các thuật ngữ chính xác
- Bao gồm cả đường dẫn phân cấp của tính năng (Ví dụ: Tiết kiệm/Tiết kiệm Thịnh Vượng linh hoạt/Giới thiệu chung)
- Các từ khóa phải được ngăn cách bằng dấu phẩy
"""




class AbstractQuery:
   def __init__(
      self,
      generator: Generator,
      max_retries: int = 20,
      retry_delay: float = 2.0
   ) -> None:
      self.generator = generator
      self.max_retries = max_retries
      self.retry_delay = retry_delay

   @observe(name="AbstractQuery")
   async def run(self, question: str) -> str:
      for attempt in range(self.max_retries):
         try:
            text = await self.generator.run(
               prompt=system_prompt.format(
                                          question=question,
                                          ),
               temperature=0.1
            )

            return text.strip('```').strip() if text.startswith('```') else text.strip()
         
         
         except Exception as e:
            if attempt < self.max_retries - 1:
               logger.warning(f"Lỗi khi gọi Enrichment (lần thử {attempt + 1}/{self.max_retries}): {str(e)}")
               await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
            else:
               logger.error("Đã hết số lần thử lại. Không thể tăng cường.")
               return OVERLOAD_MESSSAGE