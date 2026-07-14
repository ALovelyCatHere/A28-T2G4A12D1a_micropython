from machine import UART, Pin
import time

class A28Module:
    def __init__(self, uart_id, tx_pin, rx_pin, md0_pin, md1_pin, aux_pin, baudrate=9600):
        self.uart = UART(uart_id, baudrate=baudrate, tx=Pin(tx_pin), rx=Pin(rx_pin), timeout=100)
        self.md0 = Pin(md0_pin, Pin.OUT)
        self.md1 = Pin(md1_pin, Pin.OUT)
        self.aux = Pin(aux_pin, Pin.IN)
        self.md0.value(0)
        self.md1.value(0)

        self._my_addr_high = 0x12 # 记录自己的地址高位
        self._my_addr_low  = 0x34 # 记录自己的地址低位
        self._p2p_mode = False    # 是否为硬件点对点模式

        self._wait_for_idle()

    def _wait_for_idle(self):
        start = time.ticks_ms()
        while self.aux.value() == 0:
            if time.ticks_diff(time.ticks_ms(), start) > 2000:
                break
            time.sleep_ms(5)
        time.sleep_ms(2)

    def _set_mode(self, md0_val, md1_val):
        self._wait_for_idle()
        time.sleep_ms(3)
        self.md0.value(md0_val)
        self.md1.value(md1_val)
        time.sleep_ms(3)
        self._wait_for_idle()

    def _send_cmd(self, cmd_bytes, expected_response_len=0, timeout_ms=50):
        self.uart.write(cmd_bytes)
        if expected_response_len > 0:
            start = time.ticks_ms()
            while self.uart.any() < expected_response_len:
                if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                    return None
                time.sleep_ms(1)
            return self.uart.read(expected_response_len)
        return None

    def enter_config_mode(self):
        self._set_mode(1, 1)

    def exit_config_mode(self):
        self._set_mode(0, 0)

    def set_config(self, addr_high=0x12, addr_low=0x34, baudrate=9600, parity='none',
                   air_speed=0, channel=0x00, transparent_mode=True):
        # 更新本地记录地址，便于点对点模式下自我识别
        self._my_addr_high = addr_high
        self._my_addr_low  = addr_low

        parity_map = {'none': 0b00, 'odd': 0b01, 'even': 0b10}
        parity_val = parity_map.get(parity, 0b00)
        baud_map = {1200: 0b000, 2400: 0b001, 4800: 0b010, 9600: 0b011,
                    19200: 0b100, 38400: 0b101, 57600: 0b110, 115200: 0b111}
        baud_val = baud_map.get(baudrate, 0b011)
        air_val = air_speed & 0b111
        speed_byte = (parity_val << 6) | (baud_val << 3) | air_val

        # 透明传输模式(0) vs 点对点(1) 对应 OPTION 第7位
        opt_mode = 0b0 if transparent_mode else 0b1
        option_byte = (opt_mode << 7) | 0x03

        self.enter_config_mode()
        cmd = bytes([0xC0, addr_high, addr_low, speed_byte, channel, option_byte])
        resp = self._send_cmd(cmd, expected_response_len=2, timeout_ms=100)
        self.exit_config_mode()

        if resp and resp == b'OK':
            self.uart.init(baudrate=baudrate)
            return True
        return False

    def set_point_to_point(self, enable=True):
        """
        设置模块工作在硬件点对点模式。
        开启后，发送数据必须包含目标地址，硬件会自动过滤其他设备的数据。
        """
        self._p2p_mode = enable
        # 需重新配置寄存器，将 OPTION bit7 设为 1
        # 这里不改变其他参数，仅重写 OPTION
        current_config = self.read_config()
        if current_config:
            if enable:
                # bit7 = 1
                option = (1 << 7) | 0x03
            else:
                # bit7 = 0 恢复透明广播
                option = 0x03

            self.enter_config_mode()
            # 修改 OPTION 字节，注意第 5 个字节是 CHAN，第 6 个是 OPTION
            cmd = bytes([0xC0, current_config['addr_high'], current_config['addr_low'],
                         current_config['speed'], current_config['channel'], option])
            resp = self._send_cmd(cmd, expected_response_len=2, timeout_ms=100)
            self.exit_config_mode()
            return resp == b'OK'
        return False

    def read_config(self):
        self.enter_config_mode()
        cmd = bytes([0xC1, 0xC1, 0xC1])
        resp = self._send_cmd(cmd, expected_response_len=6, timeout_ms=50)
        self.exit_config_mode()
        if resp and len(resp) == 6:
            return {'addr_high': resp[1], 'addr_low': resp[2], 'speed': resp[3],
                    'channel': resp[4], 'option': resp[5]}
        return None

    # ---------- 点对点通信接口（关键修改） ----------
    def send(self, data, target_high=None, target_low=None):
        """
        发送数据
        :param data: 字节串或字符串
        :param target_high: 目标设备地址高8位 (无参/None时默认为广播或透明模式)
        :param target_low: 目标设备地址低8位
        """
        if isinstance(data, str):
            data = data.encode('utf-8')

        if self._p2p_mode:
            # 如果开启了硬件点对点，若未指定目标地址，默认发给自己（测试用）
            if target_high is None or target_low is None:
                target_high = self._my_addr_high
                target_low = self._my_addr_low
            # 在数据头部加上目标地址(2字节)
            packet = bytes([target_high, target_low]) + data
            self.uart.write(packet)
        else:
            # 透明广播模式，不拼接头
            self.uart.write(data)

    def receive(self, max_len=256):
        """
        接收数据（包含点对点模式过滤逻辑）
        返回解析后的有效数据，若收到非发往本机数据则返回 None 并丢弃
        """
        if not self.uart.any():
            return None

        if self._p2p_mode:
            # 先读取 2 字节确认目标地址
            header = self.uart.read(2)
            if header and len(header) == 2:
                target_h, target_l = header[0], header[1]
                # 检查目标地址是否是自己
                if target_h == self._my_addr_high and target_l == self._my_addr_low:
                    # 剩下的字节是数据
                    if self.uart.any():
                        return self.uart.read(max_len)
                else:
                    # 非本机数据，清空缓存丢掉
                    self.uart.read()
            return None
        else:
            # 透明广播模式，不处理包头
            return self.uart.read(max_len)
