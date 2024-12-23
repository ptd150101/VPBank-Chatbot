from . import *
from langfuse.decorators import observe, langfuse_context
from utils.log_utils import get_logger
from schemas.api_response_schema import ChatLogicInputData
from .generator import VertexAIGenerator
from .chat_generator import VertexAIChatGenerator
from .enrichment import Enrichment
from .answer_generator import AnswerGenerator
from .document_retriever import DocumentRetriever
from .embedder import Embedder
from .translate import Translate
from .summary import Summary
from .spell_correct import InputValidator
from .routing_question import RoutingQuestion
from .database import get_db
from source.config.setting_bot import GETFLY_BOT_SETTINGS
import traceback
import json
import os
from config.env_config import (
    DEFAULT_ANSWER, CREDENTIALS_PATH,
    OVERLOAD_MESSAGE, CS_MESSAGE, NO_RELEVANT_GETFLY_MESSAGE
)
from google.oauth2.service_account import Credentials
from .single_query import SingleQuery
from .multi_query import MultiQuery
from .intent_detect import IntentDetect
from .chitchat import ChitChat

credentials = Credentials.from_service_account_file(
    CREDENTIALS_PATH,
    scopes=['https://www.googleapis.com/auth/cloud-platform']
)

logger = get_logger(__name__)


class AI_Chatbot_Service:

    def __init__(self):
        generator_pro = VertexAIGenerator(
            # model="gemini-2.0-flash-exp",
            model="gemini-1.5-pro-002",
            project_id="communi-ai",
            location="asia-southeast1",
            credentials=credentials
            )
        generator_flash = VertexAIGenerator(
            # model="gemini-2.0-flash-exp",
            model="gemini-1.5-flash-002",
            project_id="communi-ai",
            location="asia-southeast1",
            credentials=credentials
            )
        chat_generator = VertexAIChatGenerator(
            # model="gemini-2.0-flash-exp",
            model="gemini-1.5-pro-002",
            project_id="communi-ai",
            location="asia-southeast1",
            credentials=credentials
            )
        
        chat_generator_flash = VertexAIChatGenerator(
            # model="gemini-2.0-flash-exp",
            model="gemini-1.5-flash-002",
            project_id="communi-ai",
            location="asia-southeast1",
            credentials=credentials
            )

        self.summary = Summary(
            generator=generator_flash,
            max_retries=10, 
            retry_delay=2.0
        )
        self.enrichment = Enrichment(
            generator=generator_flash,
            max_retries=10, 
            retry_delay=2.0
        )
        self.db = next(get_db())
        self.document_retriever = DocumentRetriever(session=self.db)
        self.embedder = Embedder(
            url="http://35.197.153.145:8231/embed",
            batch_size=1,
            max_length=4096,
            max_retries=20,
            retry_delay=2.0 
        )
        self.answer_generator = AnswerGenerator(
            chat_generator=chat_generator_flash,
            settings=GETFLY_BOT_SETTINGS
            )
        self.spell_correct = InputValidator(
            generator=generator_flash,
            max_retries=20, 
            retry_delay=2.0
        )
        self.routing_question = RoutingQuestion(
            generator=generator_flash,
            max_retries=20, 
            retry_delay=2.0
        )
        self.translate = Translate(
            generator=generator_flash,
            max_retries=20, 
            retry_delay=2.0
        )
        self.single_query = SingleQuery(
            generator=generator_flash,
            max_retries=20, 
            retry_delay=2.0
        )
        self.multi_query = MultiQuery(
            generator=generator_flash,
            max_retries=20, 
            retry_delay=2.0
        )

        self.intent_detect = IntentDetect(
            generator=generator_flash,
            max_retries=20, 
            retry_delay=2.0
        )

        self.chitchat = ChitChat(
            generator=generator_flash,
            max_retries=20, 
            retry_delay=2.0
        )

    @observe(name="AI_Chatbot_Service_Answer")
    async def create_response(self, user_data: ChatLogicInputData):
        langfuse_context.update_current_trace(
            user_id=user_data.user_name,
            tags=["STAGING", "VPBank"]
        )
        try:
            original_question = user_data.content
            summary_history = user_data.summary
            corrected_question = await self.spell_correct.run(question=original_question)

            if corrected_question.get("routing", "") == "UNCORRECT":
                return -202, [{"type": "text", "content": DEFAULT_ANSWER}], user_data.summary

            user_intent = await self.intent_detect.run(corrected_question.get('correct_query', ''))
            responses = []
            if user_intent.get("intent_id", "") == 1:
                responses.append({
                    "type": "quick_reply",
                    "content": "1"
                })
                return 200, responses, summary_history
            if user_intent.get("intent_id", "") == 2:
                responses.append({
                    "type": "quick_reply",
                    "content": "2"
                })
                return 200, responses, summary_history
            if user_intent.get("intent_id", "") == 3:
                responses.append({
                    "type": "quick_reply",
                    "content": "3"
                })
                return 200, responses, summary_history
            if user_intent.get("intent_id", "") == 3:
                responses.append({
                    "type": "quick_reply",
                    "content": "3"
                })
                return 200, responses, summary_history

            if user_intent.get("intent_id", "") == 4:
                responses.append({
                    "type": "quick_reply",
                    "content": "4"
                })
                return 200, responses, summary_history




            routing_question = await self.routing_question.run(user_data=user_data, question=corrected_question.get('correct_query', ''))
            if routing_question.get("is_social_conversation") is True:
                chitchat = await self.chitchat.run(question=corrected_question.get('correct_query', ''))
                return 200, [{"type": "text", "content": chitchat}], user_data.summary

            if routing_question.get("customer_service_request") is True:
                return 200, [{"type": "text", "content": CS_MESSAGE}], user_data.summary
    
            else:
                if routing_question.get("is_vpbank_relevant", "") < 3:
                    return 200, [{"type": "text", "content": NO_RELEVANT_GETFLY_MESSAGE}], user_data.summary

                # Tối ưu hóa logic cho việc lấy tài liệu
                relevant_documents, seen_ids, backup_relevant = [], set(), []
                if routing_question.get("complexity_score", "") > 5:
                    multi_query = await self.multi_query.run(user_data=user_data, question=corrected_question['correct_query'])
                    child_prompts = multi_query.get('child_prompt_list', [])
                    original_query = corrected_question['correct_query']
                else:
                    single_query = (await self.single_query.run(user_data=user_data, question=corrected_question['correct_query'])).get("rewrite_prompt", "")
                    child_prompts = [single_query]
                    original_query = single_query

                for query in child_prompts:
                    documents = self.document_retriever.run(query=query, threshold=0.35)
                    backup_documents = documents['backup_rerank']
                    for doc in documents['final_rerank']:
                        if doc['id'] not in seen_ids:
                            relevant_documents.append(doc)
                            seen_ids.add(doc['id'])

                    for doc in backup_documents:
                        if doc['id'] not in seen_ids:
                            backup_relevant.append(doc)
                            seen_ids.add(doc['id'])


                if not relevant_documents:
                    documents = self.document_retriever.run(query=corrected_question.get('correct_query', ''), threshold=0.35)
                    for doc in documents['final_rerank']:
                        if doc['id'] not in seen_ids:
                            relevant_documents.append(doc)
                            seen_ids.add(doc['id'])
                    for doc in backup_documents:
                        if doc['id'] not in seen_ids:
                            backup_relevant.append(doc)
                            seen_ids.add(doc['id'])


                # if not relevant_documents:
                #     relevant_documents = sorted(
                #                         backup_relevant,  # Sử dụng danh sách đã được lọc
                #                         key=lambda item: item['cross_score'],
                #                         reverse=True  # Sắp xếp theo thứ tự giảm dần
                #                     )[:3]

                # Gọi answer_generator với relevant_documents (có thể rỗng hoặc có dữ liệu)
                answer = await self.answer_generator.run(
                    messages=user_data.histories,
                    relevant_documents=sorted(relevant_documents, key=lambda doc: doc['cross_score'], reverse=False) if relevant_documents else [],
                    summary_history=summary_history,
                    original_query=original_query,
                )

                is_query_answerable = answer.get("is_query_answerable", "")
                if is_query_answerable is False:
                    return 200, [{"type": "text", "content": DEFAULT_ANSWER}], user_data.summary

                original_answer = answer.get("original_answer", "")
                references = answer.get("references", [])

                final_answer = answer.get("final_answer", "")
                responses.append({
                    "type": "text",
                    "content": self.answer_generator.format_answer(original_answer).get('answer', '')
                })


                # Tạo references với link nhúng
                if references:
                    # Dictionary để lưu trữ {link: title} và tránh duplicate
                    link_titles = {}
                    
                    for ref in references:
                        content_lines = ref.get('page_content', '').split('\n')
                        first_header = None
                        last_header = None
                        
                        # Thu thập header đầu tiên và cuối cùng
                        for line in content_lines:
                            line = line.strip()
                            if line.startswith('#'):
                                # Loại bỏ dấu # và khoảng trắng
                                clean_header = line.lstrip('# *').rstrip('*')
                                if clean_header:  # Chỉ thêm nếu header không rỗng
                                    if first_header is None:
                                        first_header = clean_header
                                    last_header = clean_header
                        
                        if first_header and last_header:
                            # Nếu chỉ có một header, sử dụng header đó
                            if first_header == last_header:
                                title = first_header
                            else:
                                title = f"{first_header} › {last_header}"
                            
                            title = title.replace('**', '').replace('/', '')
                            
                            link = ref.get('chunk_id', '')
                            full_reference = f"- [{title}]({link})"
                            
                            if link:
                                # Lưu title mới nhất cho mỗi link
                                link_titles[link] = title
                    
                    if link_titles:
                        # Tạo references_str từ dictionary đã được lọc duplicate
                        references_str = "\n".join(f"- [{title}]({link})" for link, title in link_titles.items())
                        responses.append({
                            "type": "text",
                            "content": f"Xem thêm:\n{references_str}"
                        })




                # Xử lý phản hồi hình ảnh và video
                for doc in relevant_documents:
                    if doc.get('images'):
                        responses.append({"type": "images", "content": list(set(doc['images']))})
                    if doc.get('videos'):
                        responses.append({"type": "videos", "content": list(set(doc['videos']))})

                summary_history = await self.create_summary(
                    messages=user_data.histories,
                    previous_summary=summary_history,
                    assistant_message=final_answer
                )

                user_data.summary = summary_history
                return 200, responses, summary_history

        except Exception as e:
            logger.error(f"Error in main create_response: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.info("No data found")
            return -202, [{"type": "text", "content": OVERLOAD_MESSAGE}], user_data.summary



    @observe(name="AI_Chatbot_Service_Summary")
    async def create_summary(self, messages, previous_summary, assistant_message):
        try:
            summary = await self.summary.run(messages=messages, 
                                        previous_summary=previous_summary,
                                        assistant_message=assistant_message)
            return summary
        except Exception as e:
            logger.error(f"Error in main create_summary: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.info("No data found")
            return ""