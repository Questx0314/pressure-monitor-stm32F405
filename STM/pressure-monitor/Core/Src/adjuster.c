#include "adjuster.h"
#include "usbd_cdc_if.h"
#include "main.h"


#define NUM_CURVES 4
// 曲线控制点的数量
#define NUM_POINTS 10

#define MAX_STRING_LEN 6  // 确保最大字符串长度，包括 '\0'
char type_group[NUM_CURVES][MAX_STRING_LEN] = {
    "F-H",  //前后
    "L-R",  //左右
    "ZBL1", //指拨轮1
    "ZBL2"  //指拨轮2
};

float points_data[NUM_CURVES * NUM_POINTS] = {
    0, 0, 25, 25, 50, 50, 75, 75, 100, 100,   // 第一行
    100, 100, 75, 75, 50, 50, 25, 25, 0, 0,   // 第二行
    0, 50, 25, 50, 50, 50, 75, 50, 100, 50,   // 第三行
    50, 0, 50, 25, 50, 50, 50, 75, 50, 100    // 第四行
};

/* 用户变量起始地址 */
#define FLASH_ADDR_USER_VAR   0x08080000  
#define FLASH_ADDR_CONTROL 0x08080200   //假设在这里开始放手柄的曲线数据
/*用户变量扇区 */
#define USER_VAR_SECTOR FLASH_SECTOR_8    //扇区和内存位置要对应上，否则会出现擦除和读取错误，通过查芯片手册

/* 用户变量区的大小 */
#define FLASH_SIZE_USER_VAR   0x00020000   //128K
/*用户变量区实际大小*/
#define DATA_BUF_SIZE ((uint32_t)0x800)   //1K最好不要太大


//////////////////////////////////////////////////////////////////////////////////////////////////////

// 发送消息数据长度
#define MAX_TX_LEN 128

void SendResponse(char* response)
{
  uint8_t buffer[MAX_TX_LEN];
  uint16_t len = snprintf((char*)buffer, sizeof(buffer), "%s", response);
  CDC_Transmit_HS(buffer, len);  // 通过 USB 发送消息
}

void ReadPointsFromFlash(float* curves_data, uint32_t src_address, uint32_t data_length)
{
    // 确保传入的地址是4字节对齐的
    if (src_address % 4 != 0) {
        // 地址不对齐，返回错误或进行处理
        return;
    }

    memcpy(curves_data, (void*)src_address, data_length);
}

HAL_StatusTypeDef EraseUserFlash(uint32_t flash_sector)
{
    HAL_FLASH_Unlock();

    FLASH_EraseInitTypeDef eraseInitStruct;
    uint32_t sectorError;

    eraseInitStruct.TypeErase = FLASH_TYPEERASE_SECTORS;
    eraseInitStruct.VoltageRange = FLASH_VOLTAGE_RANGE_3;
    eraseInitStruct.Sector = flash_sector;
    eraseInitStruct.NbSectors = 1;

    if (HAL_FLASHEx_Erase(&eraseInitStruct, &sectorError) != HAL_OK) {
        SendResponse("Erase failed");
        HAL_FLASH_Lock();
        return HAL_ERROR;
    }
    HAL_FLASH_Lock();
    return HAL_OK;
}

HAL_StatusTypeDef Flash_Write(uint32_t destAddress, uint8_t* srcAddress, uint32_t length) 
{
    HAL_StatusTypeDef status = HAL_OK;
    uint32_t i = 0;
    uint32_t wordData;

    // Unlock Flash for writing
    HAL_FLASH_Unlock();

    // Ensure address and length are aligned
    if ((destAddress % 4 != 0) || (length % 4 != 0)) {
        SendResponse("No address");
        HAL_FLASH_Lock();
        return HAL_ERROR;
    }

    // Write data word-by-word
    for (i = 0; i < length; i += 4) {
        wordData = *((uint32_t *)(srcAddress + i)); // Convert 4 bytes to 32-bit word
        status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, destAddress + i, wordData);
        if (status != HAL_OK) {
            SendResponse("Write failed");
            HAL_FLASH_Lock();
            return HAL_ERROR;
        }
    }

    // Lock Flash after operation
    HAL_FLASH_Lock();
    return HAL_OK;
}

HAL_StatusTypeDef ModifyFlash(uint32_t start_address,uint8_t* data,uint32_t address_offset,uint32_t data_length,uint32_t batch_size)
{
    if (data_length > DATA_BUF_SIZE)
    {
        SendResponse("data buf overflow");
        return HAL_ERROR;
    }

    // 取出flash中的数据
    uint8_t data_buf[DATA_BUF_SIZE] = {0};
    memset(data_buf,0,DATA_BUF_SIZE);
    memcpy(data_buf,(void*)start_address,batch_size);
    
    if (EraseUserFlash(USER_VAR_SECTOR) != HAL_OK) //Remarkable
    {
        return HAL_ERROR;
    }

    // 拷贝手柄数据
    memcpy(&(data_buf[address_offset]),data,data_length);
    // SendResponse("here");
    // return HAL_OK;
    if (Flash_Write(start_address,data_buf,batch_size) != HAL_OK)
    {
        return HAL_ERROR;
    }
    return HAL_OK;
}

// 解析接收到的点数据并更新
void UpdatePoints(uint8_t* data,uint8_t curve_index)
{
    char* token = strtok((char*)data, ",");
    uint8_t point_index = 0;

    // 遍历解析点数据
    while (token != NULL && point_index < NUM_POINTS)
    {
        float value = atof(token);
        // 验证数据范围
        if (value < 0.0f || value > 100.0f) 
        {
            char detail[40];
            snprintf(detail, sizeof(detail), "Invalid value: %f at index: %d", value, point_index);
            SendResponse(detail);
            return;
        }
        // 存储有效的值到 pointsData
        points_data[point_index + curve_index*NUM_POINTS] = value;
        token = strtok(NULL, ",");
        point_index++;
    }

    // 确保数据完整
    if (point_index != NUM_POINTS)
    {
        char detail[32];
        snprintf(detail, sizeof(detail), "Expected %d points, got %d", NUM_POINTS, point_index);
        SendResponse(detail);
        return;
    }

    // 写入到 Flash
    if(ModifyFlash(FLASH_ADDR_USER_VAR,
        (uint8_t*)points_data,
        FLASH_ADDR_CONTROL - FLASH_ADDR_USER_VAR,
        sizeof(points_data),
        DATA_BUF_SIZE) == HAL_OK){SendResponse("data send success");}
}

uint8_t GetTypeIndex(uint8_t* type_name)
{
    for (uint8_t i = 0; i < NUM_CURVES; i++)
    {
        // 这里使用 strcmp 来进行完全匹配比较
        if (strncmp((char*)type_name, type_group[i],strlen(type_group[i])) == 0)  // 如果找到匹配的字符串
        {
            return i;  // 返回对应的索引
        }
    }
    return 255;
}

void SendPoints(uint8_t* type_name)
{
    uint8_t index = GetTypeIndex(type_name);  // 获取对应的索引
    if (index != 255) {
        ReadPointsFromFlash(points_data,FLASH_ADDR_CONTROL,sizeof(points_data));
        char buffer[MAX_TX_LEN];
        uint8_t len = snprintf(buffer, sizeof(buffer), "Controller send points:");

        // 读取存储在 pointsData 中的点数据并发送
        for (uint8_t i = 0; i < NUM_POINTS; i++)
        {
            if (i == 0)
            {
                len += snprintf(buffer+len,sizeof(buffer)-len,"%.2f",points_data[i + index*NUM_POINTS]);
            }
            else
            {
                len += snprintf(buffer+len,sizeof(buffer)-len,",%.2f",points_data[i + index*NUM_POINTS ]);
            }
        }
        SendResponse(buffer);
    } else {
        // 未找到类型，可能需要发送错误信息
        SendResponse("Invalid type request");
    }
}

// 处理接收的数据
void ProcessReceivedData(uint8_t* data, uint32_t len)
{
    if (strstr((char*)data, "FS connect") == (char*)data)
    {
        char msg[MAX_TX_LEN];
        memset(msg, 0, sizeof(msg));  // 清零缓冲区
        snprintf(msg,sizeof(msg),"connect success:");
        for (int i = 0; i < NUM_CURVES; i++) {
            if (i == 0) {
                strcat((char*)msg, type_group[i]);
            } else {
                strcat((char*)msg, ",");
                strcat((char*)msg, type_group[i]);
            }
        }
        SendResponse(msg);
    }
    else if (strstr((char*)data, "FS request points:") == (char*)data)
    {
        SendPoints(data + strlen("FS request points:"));  // 传递冒号后的内容进行处理
    }
    else if (strstr((char*)data, "FS:") == (char*)data)
    {
        // 提取数字部分并更新点数据
        uint8_t curve_index = GetTypeIndex(data + strlen("FS:"));
        if (curve_index == 255)
        {
            SendResponse("wrong type");
            return;
        }
        UpdatePoints(data + strlen("FS:") + strlen(type_group[curve_index]) + 1, curve_index);  // 只传输FS send points：之后的部分
    }
    else
    {
        SendResponse("Unknown command");  // 回传未识别的命令
    }
}

// 在重启单片机之后不需要插拔usb也能正确识别
void USB_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_11|GPIO_PIN_12, GPIO_PIN_RESET);

  /*Configure GPIO pin : PA8 */
  GPIO_InitStruct.Pin = GPIO_PIN_11|GPIO_PIN_12;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_OD;
  GPIO_InitStruct.Pull = GPIO_PULLDOWN;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  HAL_Delay(50);
}
