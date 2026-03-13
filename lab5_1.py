
import boto3
import os
from botocore.exceptions import ClientError, NoCredentialsError

REGION = "us-east-1"
KEY_NAME = "ec2-keypair"
KEY_FILE = os.path.join(os.path.expanduser("~"), "aws_ec2_key.pem")
AMI_ID = "ami-0b6c6ebed2801a5cb"
INSTANCE_TYPE = "t3.micro"
BUCKET_NAME = "anastasia-baliura-lab5"  
CSV_LOCAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eur_rate_2022.csv")
CSV_S3_KEY = "eur_rate_2022.csv"

def create_key_pair():
    ec2_client = boto3.client("ec2", region_name=REGION)
    try:
        key_pair = ec2_client.create_key_pair(KeyName=KEY_NAME)
        private_key = key_pair["KeyMaterial"]
        if os.path.exists(KEY_FILE):
            os.chmod(KEY_FILE, 0o600)
        with open(KEY_FILE, "w") as f:
            f.write(private_key)
        os.chmod(KEY_FILE, 0o400)
        print(f"[OK] Ключову пару '{KEY_NAME}' створено. Збережено у {KEY_FILE}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "InvalidKeyPair.Duplicate":
            print(f"[УВАГА] Ключова пара '{KEY_NAME}' вже існує. Пропускаємо створення.")
        else:
            print(f"[ПОМИЛКА] Не вдалося створити ключову пару: {e}")
    except NoCredentialsError:
        print("[ПОМИЛКА] AWS credentials не знайдено. Налаштуйте aws configure.")


def delete_key_pair():
    ec2_client = boto3.client("ec2", region_name=REGION)
    try:
        ec2_client.delete_key_pair(KeyName=KEY_NAME)
        print(f"[OK] Ключову пару '{KEY_NAME}' видалено.")
        if os.path.exists(KEY_FILE):
            os.chmod(KEY_FILE, 0o600)  
            os.remove(KEY_FILE)
            print(f"[OK] Локальний файл {KEY_FILE} видалено.")
    except ClientError as e:
        print(f"[ПОМИЛКА] Не вдалося видалити ключову пару: {e}")

def create_instance():
    ec2_client = boto3.client("ec2", region_name=REGION)
    try:
        instances = ec2_client.run_instances(
            ImageId=AMI_ID,
            MinCount=1,
            MaxCount=1,
            InstanceType=INSTANCE_TYPE,
            KeyName=KEY_NAME,
        )
        instance_id = instances["Instances"][0]["InstanceId"]
        print(f"[OK] EC2 інстанс створено. ID: {instance_id}")
        return instance_id
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "InvalidAMIID.NotFound":
            print(f"[ПОМИЛКА] AMI '{AMI_ID}' не знайдено в регіоні {REGION}.")
        elif code == "InvalidKeyPair.NotFound":
            print(f"[ПОМИЛКА] Ключова пара '{KEY_NAME}' не існує. Спочатку запустіть create_key_pair().")
        else:
            print(f"[ПОМИЛКА] Не вдалося створити інстанс: {e}")
        return None


def get_public_ip(instance_id):
    ec2_client = boto3.client("ec2", region_name=REGION)
    try:
        reservations = ec2_client.describe_instances(
            InstanceIds=[instance_id]
        ).get("Reservations")
        for reservation in reservations:
            for instance in reservation["Instances"]:
                ip = instance.get("PublicIpAddress")
                if ip:
                    print(f"[OK] Публічна IP-адреса: {ip}")
                    return ip
                else:
                    print("[УВАГА] Інстанс ще не отримав публічну IP. Зачекайте і спробуйте ще раз.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
            print(f"[ПОМИЛКА] Інстанс '{instance_id}' не знайдено.")
        else:
            print(f"[ПОМИЛКА] {e}")
    return None


def get_running_instances():
    ec2_client = boto3.client("ec2", region_name=REGION)
    try:
        reservations = ec2_client.describe_instances(Filters=[
            {"Name": "instance-state-name", "Values": ["running"]},
            {"Name": "instance-type", "Values": [INSTANCE_TYPE]},
        ]).get("Reservations")

        if not reservations:
            print("[ІНФО] Активних інстансів не знайдено.")
            return

        print(f"[OK] Активні інстанси типу {INSTANCE_TYPE}:")
        for reservation in reservations:
            for instance in reservation["Instances"]:
                print(f"  ID: {instance['InstanceId']} | "
                      f"Тип: {instance['InstanceType']} | "
                      f"Публічна IP: {instance.get('PublicIpAddress', 'N/A')} | "
                      f"Приватна IP: {instance.get('PrivateIpAddress', 'N/A')}")
    except ClientError as e:
        print(f"[ПОМИЛКА] {e}")


def stop_instance(instance_id):
    ec2_client = boto3.client("ec2", region_name=REGION)
    try:
        response = ec2_client.stop_instances(InstanceIds=[instance_id])
        state = response["StoppingInstances"][0]["CurrentState"]["Name"]
        print(f"[OK] Інстанс '{instance_id}' зупиняється. Поточний стан: {state}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
            print(f"[ПОМИЛКА] Інстанс '{instance_id}' не знайдено.")
        elif e.response["Error"]["Code"] == "IncorrectInstanceState":
            print(f"[УВАГА] Інстанс вже зупинено або перебуває у некоректному стані.")
        else:
            print(f"[ПОМИЛКА] {e}")


def terminate_instance(instance_id):
    ec2_client = boto3.client("ec2", region_name=REGION)
    try:
        response = ec2_client.terminate_instances(InstanceIds=[instance_id])
        state = response["TerminatingInstances"][0]["CurrentState"]["Name"]
        print(f"[OK] Інстанс '{instance_id}' видаляється. Поточний стан: {state}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
            print(f"[ПОМИЛКА] Інстанс '{instance_id}' не знайдено.")
        else:
            print(f"[ПОМИЛКА] {e}")

def create_bucket(bucket_name=BUCKET_NAME, region=REGION):
    s3_client = boto3.client("s3", region_name=region)
    try:
        location = {"LocationConstraint": region}
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration=location,
        )
        print(f"[OK] Бакет '{bucket_name}' успішно створено.")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "BucketAlreadyOwnedByYou":
            print(f"[УВАГА] Бакет '{bucket_name}' вже існує і належить вашому акаунту.")
        elif code == "BucketAlreadyExists":
            print(f"[ПОМИЛКА] Ім'я '{bucket_name}' вже зайняте іншим користувачем. "
                  f"Оберіть інше унікальне ім'я.")
        elif code == "InvalidBucketName":
            print(f"[ПОМИЛКА] Некоректне ім'я бакету '{bucket_name}'. "
                  f"Ім'я має містити лише малі літери, цифри та дефіси.")
        else:
            print(f"[ПОМИЛКА] Не вдалося створити бакет: {e}")


def list_buckets():
    s3_client = boto3.client("s3")
    try:
        response = s3_client.list_buckets()
        buckets = response.get("Buckets", [])
        if not buckets:
            print("[ІНФО] Бакетів не знайдено.")
            return
        print("Існуючі бакети:")
        for bucket in buckets:
            print(f"  - {bucket['Name']}  (створено: {bucket['CreationDate'].strftime('%Y-%m-%d %H:%M')})")
    except ClientError as e:
        print(f"[ПОМИЛКА] {e}")


def upload_file(file_name=CSV_LOCAL_PATH, bucket_name=BUCKET_NAME, s3_key=CSV_S3_KEY):
    s3_client = boto3.client("s3")
    try:
        if not os.path.exists(file_name):
            print(f"[ПОМИЛКА] Локальний файл '{file_name}' не знайдено.")
            return
        s3_client.upload_file(Filename=file_name, Bucket=bucket_name, Key=s3_key)
        print(f"[OK] Файл '{file_name}' завантажено у бакет '{bucket_name}' з ключем '{s3_key}'.")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "NoSuchBucket":
            print(f"[ПОМИЛКА] Бакет '{bucket_name}' не існує.")
        else:
            print(f"[ПОМИЛКА] Не вдалося завантажити файл: {e}")


def read_file_from_s3(bucket_name=BUCKET_NAME, s3_key=CSV_S3_KEY):
    try:
        import pandas as pd
    except ImportError:
        print("[ПОМИЛКА] Бібліотека pandas не встановлена. Виконайте: pip install pandas")
        return None

    s3_client = boto3.client("s3")
    try:
        obj = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        data = pd.read_csv(obj["Body"])
        print(f"[OK] Файл '{s3_key}' зчитано з бакету '{bucket_name}'.")
        print("Перші 5 рядків:")
        print(data.head())
        return data
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "NoSuchKey":
            print(f"[ПОМИЛКА] Файл '{s3_key}' не знайдено у бакеті '{bucket_name}'.")
        elif code == "NoSuchBucket":
            print(f"[ПОМИЛКА] Бакет '{bucket_name}' не існує.")
        else:
            print(f"[ПОМИЛКА] Не вдалося зчитати файл: {e}")
        return None


def delete_bucket(bucket_name=BUCKET_NAME):
    s3_client = boto3.client("s3")
    try:
        objects = s3_client.list_objects_v2(Bucket=bucket_name)
        if objects.get("KeyCount", 0) > 0:
            print(f"[ПОМИЛКА] Бакет '{bucket_name}' не порожній. "
                  f"Видаліть всі об'єкти перед видаленням бакету.")
            return
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"[OK] Бакет '{bucket_name}' успішно видалено.")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "NoSuchBucket":
            print(f"[ПОМИЛКА] Бакет '{bucket_name}' не існує.")
        else:
            print(f"[ПОМИЛКА] {e}")


if __name__ == "__main__":

    print("\n[1] Створення ключової пари")
    create_key_pair()

    print("\n[2] Створення EC2 інстансу")
    instance_id = create_instance()

    if instance_id:
        print("\n[3] Отримання публічної IP-адреси")
        get_public_ip(instance_id)

        print("\n[4] Список активних інстансів")
        get_running_instances()

        print("\n[5] Зупинка інстансу")
        stop_instance(instance_id)

        print("\n[6] Видалення інстансу")
        terminate_instance(instance_id)

    print("\n[7] Видалення ключової пари")
    delete_key_pair()

    
    print("\n[8] Створення S3 бакету")
    create_bucket()

    print("\n[9] Список бакетів")
    list_buckets()

    print("\n[10] Завантаження eur_rate_2022.csv на S3")
    upload_file()

    print("\n[11] Читання eur_rate_2022.csv з S3")
    read_file_from_s3()

    print("\n[12] Тест виключення: читання неіснуючого файлу")
    read_file_from_s3(s3_key="nonexistent_file.csv")

    print("\n[13] Тест виключення: створення бакету з тим самим ім'ям")
    create_bucket()

    print("\n[14] Тест виключення: видалення непорожнього бакету")
    delete_bucket()

    print("\nГотово!")