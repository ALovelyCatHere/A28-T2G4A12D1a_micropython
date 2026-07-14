# A28-T2G4A12D1a MicroPython Driver

MicroPython 驱动，适用于泽耀 (A-shining) A28-T2G4A12D1a 2.4GHz 15mW 全双工无线串口模块。

## <span class="emoji emoji1f680"></span> 主要特性

- 支持 **透明广播**、**半双工**、**全双工** 通信模式
- 支持 **硬件点对点** (Point-to-Point) 过滤通信
- 全功能支持配置：地址、波特率、校验位、信道、空速等
- **严格遵循 PDF 时序图**，通过 AUX 引脚进行空闲状态检测
- 适配 ESP32, RP2040 (树莓派 Pico), ESP8266 等支持 MicroPython 的 MCU

## <span class="emoji emoji1f4e6"></span> 硬件接线 (Hardware Connection)

| 模块引脚 (A28) | MCU 引脚说明 | 注意 |
| :--- | :--- | :--- |
| **MD0** | GPIO | 状态控制引脚 1 |
| **MD1** | GPIO | 状态控制引脚 2 |
| **RXD** | MCU **TX** | 模块接收，接外部 TX |
| **TXD** | MCU **RX** | 模块发送，接外部 RX |
| **AUX** | GPIO (Input) | 状态指示引脚 (强烈建议接) |
| **VCC** | 3.3V - 5.5V | 模块内置 LDO |
| **GND** | GND | 共地 |

## 🧰 快速使用 (Quick Start)

### 1. 基础配置

python
from a28_module import A28Module
from machine import Pin

radio = A28Module(
    uart_id=2,
    tx_pin=17,      # 接模块 RXD
    rx_pin=16,      # 接模块 TXD
    md0_pin=15,
    md1_pin=2,
    aux_pin=4)

### 2.点对点（一对一）通信模式
# 配置模块：地址 0x1234，波特率 9600，信道 0
radio.set_config(addr_high=0x12, addr_low=0x34, baudrate=9600, channel=0x00)
# 接收端设置
radio.set_config(addr_high=0xAA, addr_low=0x55)
radio.set_point_to_point(enable=True)

# 发送端设置 (目标接收端地址为 0xBB66)
radio.send("Hello World", target_high=0xBB, target_low=0x66)

# 接收端读取 (自动过滤非本机地址的数据包)
data = radio.receive()

API 参考

· enter_config_mode() / exit_config_mode() : 进入/退出休眠配置状态
· set_config(...) : 修改模块参数并掉电保存
· read_config() : 读取当前模块配置参数
· set_point_to_point(enable=True) : 开启/关闭硬件点对点过滤
· send(data, target_high=None, target_low=None) : 发送数据
· receive(max_len=256) : 接收数据，点对点模式下自动过滤地址
· reset() : 硬件复位模块
· read_rssi() : 读取当前接收信号的 RSSI 值

关于 Power (功率) 说明：set_config方法中我特意去掉了功率配置，因为 PDF 文档没有给出控制功率的 OPTION 寄存器位。有极个别开发者可能会问“怎么调成 12dBm 最大功率”,所以根据手册 6.2 节，功率由内部硬件默认决定，OPTION 寄存器仅定义了 Bit7 控制模式，其余保留位不应随意修改以防模块异常

本人是畜中牲，勿扰!!!
