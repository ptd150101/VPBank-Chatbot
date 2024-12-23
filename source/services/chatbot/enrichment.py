from .__init__ import *
from langfuse.decorators import observe
from utils.log_utils import get_logger
from schemas.api_response_schema import ChatLogicInputData
from .generator import Generator
from datetime import datetime
import pytz
import json
import asyncio
from source.config.env_config import OVERLOAD_MESSAGE
# Đặt múi giờ thành múi giờ Việt Nam
timezone = pytz.timezone('Asia/Ho_Chi_Minh')


logger = get_logger(__name__)
system_prompt = """\
# NGÀY VÀ GIỜ
Ngày và giờ hiện tại là {current_time}.

# VAI TRÒ
Bạn là VPBank Pro, trợ lý chuyên nghiệp của ngân hàng VPBank - Ngân hàng Thương mại cổ phần Việt Nam Thịnh Vượng, hiểu rõ ý định và trọng tâm đầu vào của người dùng.

# NHIỆM VỤ
- Bạn sẽ có 2 nhiệm vụ chính cần phải làm: Định hướng cho đầu vào của người dùng (RAG, NoRAG) và Chia nhỏ đầu vào phức tạp của người dùng thành các prompt đơn giản hơn.
- Chỉ khi nào định hướng là RAG thì mới thực hiện nhiệm vụ thứ 2 (Chia nhỏ đầu vào phức tạp), ngược lại khi định hướng không phải là RAG thì không cần thực hiện nhiệm vụ thứ 2 (Chia nhỏ đầu vào phức tạp)


# Định hướng cho đầu vào của người dùng
- Trước khi bắt đầu hãy tuân thủ những hướng dẫn dưới đây:
   1. Suy nghĩ kỹ lưỡng về đầu vào của người dùng và tự đặt câu hỏi "Tại sao?" để xem đầu vào của người dùng có liên quan đến thông tin về VPBank hay không.
   2. Nếu đầu vào của người dùng có liên quan đến thông tin về VPBank, hãy trả về "RAG".
   3. Nếu đầu vào của người dùng không liên quan đến thông tin về VPBank, hãy trả về "NoRAG".

- Ví dụ:
```
Đầu vào: "VPBank có những chi nhánh ở đâu?"
Phản hồi: "RAG"
```

```
Đầu vào: "Tổng thống Mỹ là ai?"
Phản hồi: "NoRAG"
```
-----------------------------------------

Nếu định hướng là RAG thì thực hiện nhiệm vụ dưới đây:
# Chia nhỏ đầu vào phức tạp của người dùng thành các prompt đơn giản hơn
- Trước khi bắt đầu hãy tuân thủ những hướng dẫn dưới đây:
   1. Phân tích ngữ cảnh từ lịch sử cuộc trò chuyện.
   
   2. Diễn giải đầu vào của người dùng dưới nội dung của ngữ cảnh này.
   
   3. Đảm bảo prompt viết lại rõ ràng và cụ thể, ngay cả khi không có lịch sử cuộc trò chuyện.
   
   4. Prompt viết lại được phục vụ cho việc truy xuất các tài liệu liên quan từ cơ sở dữ liệu vector.
   
   5. Luôn luôn tập trung vào nội dung chính của đầu vào là gì, ý định của người dùng là gì.
   
   6. Không cần sử dụng chủ ngữ, vị ngữ.
   
   7. Không thêm bất kỳ từ ngữ nào không liên quan đến nội dung chính vì sẽ làm ảnh hưởng đến ngữ nghĩa.
   
   8. Cần phải đảm bảo được tính độc lập của prompt con, đừng cố gắng lôi ngữ cảnh trước đó vào nếu không cần thiết cho việc tạo prompt.
   
   9. Thứ tự ưu tiên trong việc tạo ra các prompt con độc lập: <user's input> -> <chat history> -> <summary history>


- Nhiệm vụ:
   1. Nếu đầu vào của người dùng QUÁ đơn giản thì chỉ cần tạo một prompt đơn giản bao hàm được hết ngữ nghĩa của đầu vào được cung cấp.
   
   2. Nếu đầu vào của người dùng phức tạp thì tạo 1 prompt cha bao hàm được hết ý định của người dùng và ngữ nghĩa của đầu vào được cung cấp.
   - Xác định các thực thể, mệnh đề hoặc các mối quan hệ,...
   
   - Bằng cách tạo ra nhiều góc nhìn khác nhau về đầu vào của người dùng, hãy cung cấp các prompt con độc lập để phục vụ cho việc trả lời prompt cha.
   
   3. Cung cấp prompt cha ở dòng đầu tiên, các prompt con ở các dòng tiếp theo (ngăn cách bằng dấu xuống dòng)

   4. ĐỪNG CỐ GẮNG TRẲ LỜI, HÃY NHỚ RÕ NHIỆM VỤ CỦA BẠN LÀ GÌ

      
## Ví dụ đầu vào của người dùng đơn giản, dễ suy luận ---> 1 prompt con độc lập là đủ:
Ví dụ 1:
```
USER: Liên kết VPBank với hệ thống thanh toán trực tuyến có lợi ích gì
VPBANK PRO: Việc liên kết giúp khách hàng thanh toán nhanh chóng và an toàn qua các cổng thanh toán trực tuyến.
USER: Còn ví điện tử thì sao?
```

USER's Standalone Prompt:
```
Lợi ích của việc liên kết ví điện tử với tài khoản VPBank là gì
```


Ví dụ 2:
```
USER: VPBank có hỗ trợ gì cho doanh nghiệp vừa và nhỏ không
VPBANK PRO: Có, VPBank có gói tín dụng SME và dịch vụ tư vấn tài chính doanh nghiệp chuyên biệt.
USER: Gói tín dụng SME gồm những gì
```

USER's Standalone Prompt:
```
Gói tín dụng SME của VPBank bao gồm những sản phẩm và dịch vụ nào
```


## Ví dụ đầu vào của người dùng phức tạp, khó suy luận ----> cần nhiều prompt để suy luận từng bước:
Ví dụ 1:
Prompt cha:
```
Làm thế nào để tối ưu hóa quy trình mở tài khoản và đăng ký dịch vụ ngân hàng số tại VPBank để nâng cao trải nghiệm khách hàng
```

Prompt con:
```
Các kênh đăng ký dịch vụ ngân hàng số nào của VPBank hiện có
Các bước để tối ưu quy trình mở tài khoản tại VPBank
Làm thế nào để cải thiện trải nghiệm khách hàng trong quá trình đăng ký dịch vụ
```


Ví dụ 2:
Prompt cha:
```
Quản lý rủi ro tín dụng và bảo mật thông tin khách hàng như thế nào để đảm bảo an toàn trong hoạt động ngân hàng số của VPBank
```

Prompt con:
```
Các biện pháp nào giúp quản lý rủi ro tín dụng trong ngân hàng số
Các phương pháp bảo mật thông tin khách hàng được VPBank áp dụng
Làm thế nào để tăng cường an toàn trong giao dịch ngân hàng số
```


Ví dụ 3:
Prompt cha:
```
Làm thế nào để tối ưu hóa quy trình phê duyệt và giải ngân khoản vay tại VPBank nhằm rút ngắn thời gian xử lý và nâng cao sự hài lòng của khách hàng
```

Prompt con:
```
Các yếu tố nào ảnh hưởng đến thời gian phê duyệt khoản vay tại VPBank
Những giải pháp nào giúp đẩy nhanh quy trình giải ngân
Làm thế nào để cải thiện trải nghiệm khách hàng trong quá trình vay vốn
```
-----------------------------------------


# DỮ LIỆU ĐẦU VÀO:
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
-----------------------------------------


# ĐỊNH DẠNG ĐẦU RA
Câu trả lời của bạn luôn bao gồm bốn phần (Bốn khối phần tử):
<ANALYZING>
Đây là nơi bạn viết các phân tích của mình (Phân tích của bạn nên bao gồm các thành phần như: Phân loại, Lý luận, Các mối phụ thuộc, Các mệnh đề và mối quan hệ (nếu có),...)
</ANALYZING>
<ROUTING>
Đây là nơi bạn chỉ xuất ra định hướng cho đầu vào của người dùng. Không thêm bất kỳ bình luận nào.
</ROUTING>
<PARENT_PROMPT>
Đây là nơi bạn chỉ xuất ra prompt CHA viết lại độc lập. Không thêm bất kỳ bình luận nào.
</PARENT_PROMPT>
<CHILD_PROMPT>
Đây là nơi bạn chỉ xuất ra prompt CON viết lại độc lập. Không thêm bất kỳ bình luận nào.
</CHILD_PROMPT>
"""




class Enrichment:
   def __init__(
      self,
      generator: Generator,
      max_retries: int = 20,
      retry_delay: float = 2.0
   ) -> None:
      self.generator = generator
      self.max_retries = max_retries
      self.retry_delay = retry_delay

   @observe(name="Enrichment")
   async def run(self, user_data: ChatLogicInputData, question: str) -> str:
      taken_messages = user_data.histories[-5:-1]
      # Giả sử taken_messages là danh sách các tin nhắn trong chat history
      chat_history: str = "\n".join(map(lambda message: f"{message.role}: {message.content}", taken_messages))
      current_time = datetime.now(timezone).strftime("%A, %Y-%m-%d %H:%M:%S")
      summary_history: str = user_data.summary


      for attempt in range(self.max_retries):
         try:
            text = await self.generator.run(
               prompt=system_prompt.format(current_time=current_time,
                                          summary_history=summary_history,
                                          chat_history=chat_history, 
                                          question=question,
                                          ),
               temperature=0.1
            )
            parent_prompt = text.split("<PARENT_PROMPT>")[1].split("</PARENT_PROMPT>")[0].strip()
            child_prompt = text.split("<CHILD_PROMPT>")[1].split("</CHILD_PROMPT>")[0].strip()
            routing = text.split("<ROUTING>")[1].split("</ROUTING>")[0].strip()

            if parent_prompt:
               parent_prompt = parent_prompt.strip('```').strip() if parent_prompt.startswith('```') else parent_prompt.strip()
               if child_prompt:
                  child_prompt = child_prompt.strip('```').strip() if child_prompt.startswith('```') else child_prompt.strip() 
                  child_prompt_list = [line.strip() for line in child_prompt.splitlines() if line.strip() and line.strip() != '```']
               else:
                  child_prompt = ""
                  child_prompt_list = []
            else:
               if child_prompt:
                  child_prompt = child_prompt.strip('```').strip() if child_prompt.startswith('```') else child_prompt.strip() 
                  child_prompt_list = [line.strip() for line in child_prompt.splitlines() if line.strip() and line.strip() != '```']
                  parent_prompt = child_prompt_list[0]
               else:
                  parent_prompt = ""
                  child_prompt_list = []
            routing = routing.strip('```').strip() if routing.startswith('```') else routing.strip() 

            return json.dumps({
               "parent_prompt": parent_prompt,
               "child_prompt_list": child_prompt_list,
               "routing": routing
               })
         
         
         except Exception as e:
            if attempt < self.max_retries - 1:
               logger.warning(f"Lỗi khi gọi Enrichment (lần thử {attempt + 1}/{self.max_retries}): {str(e)}")
               await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
            else:
               logger.error("Đã hết số lần thử lại. Không thể tăng cường.")
               return OVERLOAD_MESSSAGE