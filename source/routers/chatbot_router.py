import asyncio
import aiohttp
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from schemas.api_response_schema import ChatLogicInputData, ChatMessageRole, ChatMessage, make_response
from source.services.chatbot.chatbot_ai import AI_Chatbot_Service
from utils.log_utils import get_logger
from .database import SessionLocal, User, Thread, ChatHistory  # Import từ file database.py
from datetime import datetime, timedelta
import json
import os
import subprocess
import pytz




THUMBNAIL_DIR = "static/thumbnails"
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

logger = get_logger(__name__)
chat_router = APIRouter()


ai_chatbot = AI_Chatbot_Service()

# Lưu trữ các thread đã tạo
threads = {}

# Biến toàn cục để lưu trữ lịch sử cuộc trò chuyện
conversation_history = {}
# Giả sử histories được lưu trong session state hoặc một biến toàn cục khác
histories = []

@chat_router.post("/chat")
async def create_answer_eng(user_data: ChatLogicInputData):
    try:
        if not user_data.content:
            logger.info("Empty Question")
            return make_response(-502, content="Empty content", summary_history="None")
        status_code, chatbot_answer, summary_history = await ai_chatbot.create_response(user_data)

        final_answer = make_response(status_code, content=chatbot_answer, summary_history=summary_history)
        # logger.info(f"Final answer: {final_answer}")

    except Exception as e:
        chatbot_answer = f"Error in logic function: {e}"
        final_answer = make_response(-503, content=chatbot_answer, summary_history=summary_history)
    return final_answer


@chat_router.post("/threads")
def post_thread(request: dict):
    db = SessionLocal()
    global histories
    print("request: ", request)

    user_data = request.get('user')
    if user_data:
        # Kiểm tra xem user đã tồn tại chưa
        existing_user = db.query(User).filter(User.user_id == user_data['id']).first()
        if existing_user:
            logger.info(f"user_id {user_data['id']} đã tồn tại, không cần thêm mới.")
            user_id = existing_user.user_id  # Sử dụng user_id từ bảng users
            user_name = existing_user.display_name
        else:
            # Nếu chưa tồn tại thì thêm mới
            user = User(user_id=user_data['id'], display_name=user_data['display_name'])
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"user_id {user_data['id']} đã được thêm vào cơ sở dữ liệu.")
            user_id = user.user_id  # Sử dụng user_id từ bảng users
            user_name = user.display_name


        # Tạo một bản ghi thread mới với đúng user_id từ bảng users
        new_thread = Thread(
            user_id=user_id, 
            communi_thread_id=user_data['communi_thread_id']
        )
        db.add(new_thread)
        db.commit()
        db.refresh(new_thread)
        
        logger.info(f"Thread được tạo với thread_id: {new_thread.thread_id}")
        
    
    
    # Thêm tin nhắn từ chatbot vào histories
    assistant_message = ChatMessage(role=ChatMessageRole.ASSISTANT, content="Chào bạn, tôi là VPBank Pro - một trợ lý ảo của VPBank. Tôi có thể giúp gì cho bạn?")
    histories.append(assistant_message)
    return {
        "data": {
            "thread": {"id": new_thread.thread_id},
            "hello_message": {
                "content": assistant_message.content  # Lấy nội dung từ assistant_message
            }
        }
    }


def generate_thumbnail(video_url, output_path):
    # Lấy frame tại giây thứ 1 của video
    command = f'ffmpeg -i {video_url} -ss 00:00:01.000 -vframes 1 {output_path}'
    subprocess.call(command, shell=True)

async def typing_message(thread_id: str, app_id: str = "1vkxsq0xau7"):
    url = f"https://{app_id}.api.piscale.com/chat-bot/v1.0/threads/{thread_id}/typing"
    payload = {}
    headers = {
    'X-PiScale-Bot-Token': '6872016411071478:bvSpZ8aOS5MpmcSX0bwj1tqLvCuVmLhLJFf2cmYW'
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            return await response.json()

# Biến toàn cục để lưu trữ thông tin thẻ
info_metadata = {}

@chat_router.post("/threads/{thread_id}/chat")
async def post_thread_chat(thread_id: int, request: dict):
    global info_metadata
    print("request: ", request)
    global conversation_history


    try:
        db = SessionLocal()
        # Lấy thông tin user_id từ thread
        thread = db.query(Thread).filter(Thread.thread_id == thread_id).first()
        if not thread:
            return {"data": {"error": "Thread not found"}}
        print("thread.communi_thread_id: ", thread.communi_thread_id)
        await typing_message(thread.communi_thread_id)

        async def typing_loop():
            while True:
                await asyncio.sleep(3)
                await typing_message(thread.communi_thread_id)
        typing_task = asyncio.create_task(typing_loop())


        user_id = thread.user_id  # Lấy user_id từ thread
        user = db.query(User).filter(User.user_id == user_id).first()
        user_name = user.display_name if user else ""  # Lấy display_name từ bảng User


        # Lấy summary từ DB nếu có
        existing_history = db.query(ChatHistory).filter_by(thread_id=thread_id, user_id=user_id).first()
        summary = existing_history.summary if existing_history else ""


        # **Kiểm tra và khởi tạo lại lịch sử chat cho thread mới**
        if thread_id not in conversation_history:
            conversation_history[thread_id] = []
            logger.info(f"Khởi tạo lịch sử chat cho thread_id {thread_id} với user_id {user_id}")

            # Thêm tin nhắn chào hỏi vào cuộc hội thoại
            welcome_message = ChatMessage(role=ChatMessageRole.ASSISTANT, content="Hello, may I help you?")
            conversation_history[thread_id].append(welcome_message)

        # Thêm tin nhắn từ người dùng vào cuộc hội thoại
        user_message = ChatMessage(role=ChatMessageRole.USER, content=request["content"])
        conversation_history[thread_id].append(user_message)

        # Tạo đối tượng ChatLogicInputData từ request và thread_id
        chat_logic_input = ChatLogicInputData(
            thread_id=str(thread_id),
            content=request["content"],
            histories=conversation_history[thread_id],
            user_id=str(user_id),
            user_name=user_name,
            summary=summary
        )
        
        current_context = thread.current_context
        print("current_context: ", current_context)
        
        thread.current_context = ""
        db.commit()



        responses = []
        postback_action = request.get("postback", "")
        print("postback_action: ", postback_action)
        

        
        
        """KỊCH BẢN 1: Thanh toán cước điện thoại"""

        if postback_action in ["viettel", "vinaphone", "mobifone"]:
            if current_context == "payment_flow":
                responses.append({
                    "reply_message": {
                        "content": "Bạn có muốn đặt lịch thanh toán định kỳ hàng tháng luôn không?",  # Nội dung cho quick reply
                        "metadata": [
                            {
                                "type": "quick_reply",
                                "quick_reply": {
                                    "items": [
                                        {
                                            "label": "Có",
                                            "action": {
                                                "type": 2,
                                                "payload": "yes_schedule_monthly_payment"
                                            }
                                        },
                                        {
                                            "label": "Không",
                                            "action": {
                                                "type": 2,
                                                "payload": "no_schedule_monthly_payment"
                                            }
                                        }
                                    ]
                                }
                            }
                        ],
                        "postback": "postback_data",
                        "forward_to_cs": False
                    }
                })
                thread.current_context = "mobile_service "
                info_metadata["mobile_service"] = request.get("content", "")
                db.commit()
            elif current_context == "topup_flow":
                responses.append({
                    "reply_message": {
                        "content": "Bạn hãy chọn số tiền muốn nạp",  # Nội dung cho quick reply
                        "metadata": [
                            {
                                "type": "quick_reply",
                                "quick_reply": {
                                    "items": [
                                        {
                                            "label": "50k",
                                            "action": {
                                                "type": 2,
                                                "payload": "50k"
                                            }
                                        },
                                        {
                                            "label": "100k",
                                            "action": {
                                                "type": 2,
                                                "payload": "100k"
                                            }
                                        },
                                        {
                                            "label": "200k",
                                            "action": {
                                                "type": 2,
                                                "payload": "200k"
                                            }
                                        },
                                        {
                                            "label": "300k",
                                            "action": {
                                                "type": 2,
                                                "payload": "300k"
                                            }
                                        },
                                        {
                                            "label": "500k",
                                            "action": {
                                                "type": 2,
                                                "payload": "500k"
                                            }
                                        }
                                    ]
                                }
                            }
                        ],
                        "postback": "postback_data",
                        "forward_to_cs": False
                    }
                })
                # responses.append({
                #     "reply_message": {
                #         "content": "Bạn muốn nạp tiền bao nhiêu tiền nhỉ?",  # Nội dung cho quick reply
                #         "metadata": [],
                #         "postback": "",
                #         "forward_to_cs": False
                #     }
                # })
                thread.current_context = "topup_amount"

                """Nhà mạng"""
                info_metadata["topup_phone_service"] = request.get("content", "")
                db.commit()










        elif postback_action == "yes_schedule_monthly_payment":
            responses.append({
                "reply_message": {
                    "content": "Bạn muốn thanh toán cước định kì hàng tháng cho số điện thoại nào?",  # Nội dung cho trường hợp trả sau
                    "metadata": [],
                    "postback": "",
                    "forward_to_cs": False
                }
            })
            thread.current_context = "phone_schedule"
            db.commit()


        elif postback_action == "no_schedule_monthly_payment":
            responses.append({
                "reply_message": {
                    "content": "Bạn muốn thanh toán cước cho số điện thoại nào?",  # Nội dung cho trường hợp trả sau
                    "metadata": [],
                    "postback": "",
                    "forward_to_cs": False
                }
            })
            thread.current_context = "phone_no_schedule"
            db.commit()


        elif postback_action == "confirm_schedule_monthly_payment":
            content = f"""Cảm ơn bạn, số điện thoại {info_metadata['phone_number']} đã được đặt lịch thanh toán cước định kỳ hàng tháng"""
            responses.append({
                "reply_message": {
                    "content": content,  # Nội dung cho quick reply
                    "metadata": [],
                    "postback": "",
                    "forward_to_cs": False
                }
            })


            """# KỊCH BẢN 2: TRA CỨU TIỀN RA TIỀN VÀO TRONG VÒNG 1 THÁNG"""
        elif postback_action == "current_month":
            report_content = f"""Trong thời gian {request.get("content", "")}:
    Tổng tiền vào của bạn là: 20.347.123 đ
    Tổng tiền ra của bạn là: 15.689.000 đ
    """
            responses.append({
                "reply_message": {
                    "content": report_content,  # Nội dung cho trường hợp trả sau
                    "metadata": [],
                    "postback": "",
                    "forward_to_cs": False
                }
            })



        elif postback_action == "last_month":
            report_content = f"""Trong thời gian {request.get("content", "")}:
    Tổng tiền vào của bạn là: 30.347.123 đ
    Tổng tiền ra của bạn là: 35.689.000 đ
    """
            responses.append({
                "reply_message": {
                    "content": report_content,  # Nội dung cho trường hợp trả sau
                    "metadata": [],
                    "postback": "",
                    "forward_to_cs": False
                }
            })



            """KỊCH BẢN 3: KHÓA THẺ"""
        elif postback_action == "chargeback" or postback_action == "happy":
            card_content = f"""Bạn có chắc chắn muốn khóa thẻ {request.get("content", "")} không?:"""
            responses.append({
                "reply_message": {
                    "content": card_content,  # Nội dung cho quick reply
                    "metadata": [
                        {
                            "type": "quick_reply",
                            "quick_reply": {
                                "items": [
                                    {
                                        "label": "Có",
                                        "action": {
                                            "type": 2,
                                            "payload": "yes_lock_card"
                                        }
                                    },
                                    {
                                        "label": "Không",
                                        "action": {
                                            "type": 2,
                                            "payload": "no_lock_card"
                                        }
                                    },
                                ]
                            }
                        }
                    ],
                    "postback": "postback_data",
                    "forward_to_cs": False
                }
            })
            info_metadata[thread_id] = request.get("content", "")




        elif postback_action == "yes_lock_card":
            content = f"""Cảm ơn bạn. Thẻ {info_metadata[thread_id]} đã được khóa theo yêu cầu của bạn"""
            responses.append({
                "reply_message": {
                    "content": content,  # Nội dung cho quick reply
                    "metadata": [],
                    "postback": "",
                    "forward_to_cs": False
                }
            })


        elif postback_action == "no_lock_card" or postback_action == "cancel_lock_card" or postback_action == "no_confirm_schedule_monthly_payment":
            content = f"""Cảm ơn bạn, yêu cầu của bạn đã được hủy"""
            responses.append({
                "reply_message": {
                    "content": content,  # Nội dung cho quick reply
                    "metadata": [],
                    "postback": "",
                    "forward_to_cs": False
                }
            })




        """XỬ LÍ CONTEXT"""
        if current_context == "phone_schedule":
            # Xử lý logic cho luồng điện thoại
            responses.append({
                "reply_message": {
                    "content": f"Có phải bạn muốn thanh toán cước định kỳ hàng tháng cho số điện thoại {request.get('content', '')} (Mạng {info_metadata['mobile_service']}) phải không?",  # Nội dung cho quick reply
                    "metadata": [
                        {
                            "type": "quick_reply",
                            "quick_reply": {
                                "items": [
                                    {
                                        "label": "Có",
                                        "action": {
                                            "type": 2,
                                            "payload": "confirm_schedule_monthly_payment"
                                        }
                                    },
                                    {
                                        "label": "Không",
                                        "action": {
                                            "type": 2,
                                            "payload": "no_confirm_schedule_monthly_payment"
                                        }
                                    }
                                ]
                            }
                        }
                    ],
                    "postback": "postback_data",
                    "forward_to_cs": False
                }
            })
            info_metadata['phone_number'] = request.get('content', '')




        if current_context == "no_phone_schedule":
            # Xử lý logic cho luồng điện thoại
            responses.append({
                "reply_message": {
                    "content": f"Có phải bạn muốn thanh toán cước cho số điện thoại {request.get('content', '')} (Mạng {info_metadata['mobile_service']}) phải không?",  # Nội dung cho quick reply
                    "metadata": [
                        {
                            "type": "quick_reply",
                            "quick_reply": {
                                "items": [
                                    {
                                        "label": "Có",
                                        "action": {
                                            "type": 2,
                                            "payload": "confirm_schedule_monthly_payment"
                                        }
                                    },
                                    {
                                        "label": "Không",
                                        "action": {
                                            "type": 2,
                                            "payload": "no_confirm_schedule_monthly_payment"
                                        }
                                    }
                                ]
                            }
                        }
                    ],
                    "postback": "postback_data",
                    "forward_to_cs": False
                }
            })



        if current_context == "topup_amount":
            responses.append({
                "reply_message": {
                    "content": f"Bạn muốn nạp {request.get('content', '')} cho số điện thoại nào?",  # Nội dung cho quick reply
                    "metadata": [],
                    "postback": "",
                    "forward_to_cs": False
                }
            })

            """Số tiền"""
            thread.current_context = "topup_phone_number"
            info_metadata["topup_amount"] = request.get("content", "")
            db.commit()


        if current_context == "topup_phone_number":
            responses.append({
                "reply_message": {
                    "content": f"Cảm ơn bạn, thuê bao {request.get('content', '')} (Mạng {info_metadata['topup_phone_service']}) đã được nạp {info_metadata['topup_amount']}",  # Nội dung cho quick reply
                    "metadata": [],
                    "postback": "",
                    "forward_to_cs": False
                }
            })




        if responses:
            typing_task.cancel()
            return {"data": responses}


        final_answer = await create_answer_eng(chat_logic_input)

        # Xử lý quick reply response
        quick_reply_handled = False
        for response in final_answer.data.content:
            if response["type"] == "quick_reply" and not quick_reply_handled:
                if response["content"] == "1":
                    responses.append({
                        "reply_message": {
                            "content": "Bạn hãy chọn nhà mạng cần thanh toán cước",  # Nội dung cho quick reply
                            "metadata": [
                                {
                                    "type": "quick_reply",
                                    "quick_reply": {
                                        "items": [
                                            {
                                                "label": "Viettel",
                                                "action": {
                                                    "type": 2,
                                                    "payload": "viettel"
                                                }
                                            },
                                            {
                                                "label": "VinaPhone",
                                                "action": {
                                                    "type": 2,
                                                    "payload": "vinaphone"
                                                }
                                            },
                                            {
                                                "label": "Mobifone",
                                                "action": {
                                                    "type": 2,
                                                    "payload": "mobifone"
                                                }
                                            }
                                        ]
                                    }
                                }
                            ],
                            "postback": "postback_data",
                            "forward_to_cs": False
                        }
                    })
                    thread.current_context = "payment_flow"  # Đánh dấu context là thanh toán cước
                    db.commit()
                    quick_reply_handled = True


                if response["content"] == "2":
                    responses.append({
                        "reply_message": {
                            "content": "Bạn có 2 thẻ Credit Card này, bạn muốn khóa thẻ credit card nào:",  # Nội dung cho quick reply
                            "metadata": [
                                {
                                    "type": "quick_reply",
                                    "quick_reply": {
                                        "items": [
                                            {
                                                "label": "Chargeback: ***4637",
                                                "action": {
                                                    "type": 2,
                                                    "payload": "chargeback"
                                                }
                                            },
                                            {
                                                "label": "Happy: ***6214",
                                                "action": {
                                                    "type": 2,
                                                    "payload": "happy"
                                                }
                                            },
                                            {
                                                "label": "Hủy yêu cầu",
                                                "action": {
                                                    "type": 2,
                                                    "payload": "cancel_lock_card"
                                                }
                                            }
                                        ]
                                    }
                                }
                            ],
                            "postback": "postback_data",
                            "forward_to_cs": False
                        }
                    })
                    quick_reply_handled = True



                if response["content"] == "3":
                    try:
                        current_date = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
                        first_day_last_month = (current_date.replace(day=1) - timedelta(days=1)).replace(day=1)
                        last_day_last_month = current_date.replace(day=1) - timedelta(days=1)
                        responses.append({
                            "reply_message": {
                                "content": "Bạn muốn thống kê từ ngày ngày nào đến ngày nào?",  # Nội dung cho quick reply
                                "metadata": [
                                    {
                                        "type": "quick_reply",
                                        "quick_reply": {
                                            "items": [
                                                {
                                                    "label": f"{(current_date - timedelta(days=30)).strftime('%d/%m/%Y')} - {current_date.strftime('%d/%m/%Y')}",
                                                    "action": {
                                                        "type": 2,
                                                        "payload": "current_month"
                                                    }
                                                },
                                                {
                                                    "label": f"{first_day_last_month.strftime('%d/%m/%Y')} - {last_day_last_month.strftime('%d/%m/%Y')}",
                                                    "action": {
                                                        "type": 2,
                                                        "payload": "last_month"
                                                    }
                                                }
                                            ]
                                        }
                                    }
                                ],
                                "postback": "postback_data",
                                "forward_to_cs": False
                            }
                        })
                        quick_reply_handled = True
                    except Exception as e:
                        print(f"Lỗi khi tính toán ngày tháng: {e}")
                    

                if response["content"] == "4":
                    responses.append({
                        "reply_message": {
                            "content": "Bạn hãy chọn nhà mạng cần nạp tiền",  # Nội dung cho quick reply
                            "metadata": [
                                {
                                    "type": "quick_reply",
                                    "quick_reply": {
                                        "items": [
                                            {
                                                "label": "Viettel",
                                                "action": {
                                                    "type": 2,
                                                    "payload": "viettel"
                                                }
                                            },
                                            {
                                                "label": "VinaPhone",
                                                "action": {
                                                    "type": 2,
                                                    "payload": "vinaphone"
                                                }
                                            },
                                            {
                                                "label": "Mobifone",
                                                "action": {
                                                    "type": 2,
                                                    "payload": "mobifone"
                                                }
                                            }
                                        ]
                                    }
                                }
                            ],
                            "postback": "postback_data",
                            "forward_to_cs": False
                        }
                    })
                    thread.current_context = "topup_flow"  # Đánh dấu context là nạp tiền
                    db.commit()
                    quick_reply_handled = True





        # Xử lý text response
        for response in final_answer.data.content:
            if response["type"] == "text":
                # Cập nhật DB và conversation history
                bot_message = ChatMessage(
                    role=ChatMessageRole.ASSISTANT, 
                    content=response["content"]
                )
                conversation_history[thread_id].append(bot_message)

                if existing_history:
                    existing_history.conversation += "\n" + "\n".join([f"{msg.role}: {msg.content}" for msg in conversation_history[thread_id]])
                    existing_history.summary = final_answer.data.summary_history
                    existing_history.display_name = user_name
                    existing_history.created_at = datetime.now()
                    db.commit()
                else:
                    conversation_text = "\n".join([f"{msg.role}: {msg.content}" for msg in conversation_history[thread_id]])
                    db.add(ChatHistory(
                        thread_id=thread_id,
                        user_id=user_id,
                        display_name=user_name,
                        conversation=conversation_text,
                        summary=final_answer.data.summary_history,
                        created_at=datetime.now()
                    ))
                    db.commit()


                responses.append({
                    "reply_message": {
                        "content": str(response["content"]),
                        "metadata": [],
                        "postback": "",
                        "forward_to_cs": False
                    }
                })







        # Xử lý images response
        for response in final_answer.data.content:
            if response["type"] == "images":
                metadata = []
                for idx, image_url in enumerate(response["content"], 1):
                    metadata.append({
                        "name": f"img_{idx}.png",
                        "width": 1000,
                        "height": 1000,
                        "source_url": image_url,
                        "source_thumb_url": image_url,
                        "size": 121200,
                        "type": "image"
                    })
                responses.append({
                    "reply_message": {
                        "content": "Hình ảnh",
                        "metadata": metadata,
                        "postback": "",
                        "forward_to_cs": False
                    }
                })

        # Xử lý videos response
        for response in final_answer.data.content:
            if response["type"] == "videos":
                metadata = []
                for idx, video_url in enumerate(response["content"], 1):
                    # Tạo thumbnail cho video
                    thumbnail_filename = f"thumbnail_{thread_id}_{idx}.jpg"
                    thumbnail_path = os.path.join(THUMBNAIL_DIR, thumbnail_filename)
                    try:
                        generate_thumbnail(video_url, thumbnail_path)
                        # Tạo URL cho thumbnail (giả sử server của bạn serve static files từ thư mục static)
                        thumbnail_url = f"/static/thumbnails/{thumbnail_filename}"
                    except Exception as e:
                        logger.error(f"Error generating thumbnail: {e}")
                        thumbnail_url = video_url  # Fallback to video URL if thumbnail generation fails

                    metadata.append({
                        "name": f"video_{idx}.mp4",
                        "width": 1080,
                        "height": 1920,
                        "src_thumb_url": thumbnail_url,
                        "src_url": video_url,
                        "size": 4170635,
                        "type": "video"
                    })
                responses.append({
                    "reply_message": {
                        "content": "Video",
                        "metadata": metadata,
                        "postback": "",
                        "forward_to_cs": False
                    }
                })

        typing_task.cancel()
        return {"data": responses}
    except Exception as e:
        typing_task.cancel()
        raise e