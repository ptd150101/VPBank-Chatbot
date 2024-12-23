from pymilvus import connections, Collection
import pandas as pd

# Kết nối đến Milvus server
connections.connect(
    alias="default",
    host="10.0.0.14", 
    port="19530"
)

# Lấy collection cần xuất dữ liệu
collection_name = "Cardina_Chatbot"
collection = Collection(collection_name)

# Truy vấn tất cả dữ liệu trong collection
results = collection.query(
    expr="",  # Empty expression
    output_fields=[
        "product_id",
        "product_name",
        "sale_price",
        "original_price",
        "type",
        "link",
        "category",
    ],
    limit=collection.num_entities  # Thêm limit bằng tổng số entities trong collection
)

# Chuyển kết quả thành DataFrame
df = pd.DataFrame(results)
print(len(df))


df.to_json("cardina_chatbot.json", orient="records", force_ascii=False, indent=4)

df.to_csv("cardina_chatbot.csv", index=False, encoding='utf-8-sig')  # utf-8-sig for proper handling of Vietnamese characters

# Đóng kết nối
connections.disconnect("default")