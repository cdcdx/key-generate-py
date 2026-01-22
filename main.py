import inquirer
import argparse
import platform
import os
import sys
import time
import random
from eth_account import Account
from web3 import Web3
from loguru import logger
from questionary import Choice, select
from termcolor import cprint
from typing import List, Optional, Tuple, Dict, Any

# 网络配置常量
NETWORK_CONFIG = {
    "eth": {
        "native_symbol": "ETH",
        "native_name": "Ethereum",
        "native_decimals": 18,
        "native_url": 'https://eth.drpc.org',
        "token_contract": '0xdac17f958d2ee523a2206206994597c13d831ec7'
    },
    "base": {
        "native_symbol": "ETH",
        "native_name": "Base",
        "native_decimals": 18,
        "native_url": 'https://mainnet.base.org',
        "token_contract": '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
    },
    "bsc": {
        "native_symbol": "BNB",
        "native_name": "Binance Smart Chain",
        "native_decimals": 18,
        "native_url": 'https://bsc-rpc.publicnode.com',
        "token_contract": '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d'
    }
}

"""
以太坊钱包管理工具
支持批量生成私钥、计算地址及查询链上余额
"""

# Contract ABI
CONTRACT_ABI_TOKEN = [
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [
            {"internalType": "uint8", "name": "", "type": "uint8"}
        ],
        "stateMutability": "pure",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [
            {"internalType": "string", "name": "", "type": "string"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "name",
        "outputs": [
            {"internalType": "string", "name": "", "type": "string"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"}
        ],
        "name": "balanceOf",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [
            {"internalType": "bool", "name": "", "type": "bool"}
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    },
]

class WalletManager:
    """钱包管理类，封装钱包相关操作"""
    
    def __init__(self, name: str = ""):
        self.name = name
        self.generate_dir = "generate"
        self._ensure_generate_dir()
    
    def _ensure_generate_dir(self) -> None:
        """确保生成目录存在"""
        if not os.path.exists(self.generate_dir):
            os.makedirs(self.generate_dir, exist_ok=True)
    
    def get_wallets_filename(self) -> str:
        """获取钱包文件名"""
        return f'{self.generate_dir}/wallets-{self.name}.txt' if self.name else f'{self.generate_dir}/wallets.txt'
    
    def scan_wallet_files(self) -> List[str]:
        """扫描generate目录下的所有txt文件"""
        txt_files = []
        if os.path.exists(self.generate_dir):
            for file in os.listdir(self.generate_dir):
                if file.endswith('.txt'):
                    txt_files.append(file)
        return sorted(txt_files)
    
    def load_wallets(self) -> List[str]:
        """加载钱包数据"""
        filename = self.get_wallets_filename()
        if not os.path.exists(filename):
            return []
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except FileNotFoundError:
            logger.warning(f"未找到钱包数据文件: {filename}")
            return []
        except Exception as e:
            logger.error(f"读取钱包数据文件失败: {e}")
            return []
    
    def save_wallets(self, wallets: List[str]) -> None:
        """保存钱包数据到文件"""
        filename = self.get_wallets_filename()
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for wallet in wallets:
                    f.write(wallet + '\n')
            logger.success(f"钱包数据已保存到: {filename}")
        except Exception as e:
            logger.error(f"保存钱包数据失败: {e}")
    
    def add_private_key(self, private_key: str) -> None:
        """添加私钥到文件"""
        filename = self.get_wallets_filename()
        try:
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(private_key + '\n')
        except Exception as e:
            logger.error(f"添加私钥失败: {e}")
    
    def update_wallet_with_address(self, wallets: List[str], private_key: str, address: str) -> List[str]:
        """更新钱包数据，添加地址信息"""
        updated_wallets = []
        for wallet in wallets:
            if wallet.startswith(private_key):
                updated_wallets.append(f"{private_key},{address}")
            else:
                updated_wallets.append(wallet)
        return updated_wallets

def get_address_by_key(private_key: str) -> Optional[str]:
    """根据私钥获取地址"""
    try:
        account = Account.from_key(private_key)
        return account.address
    except Exception as e:
        logger.error(f"从私钥获取地址失败: {e}")
        return None

def is_id_valid(id: int, runeq: List[int], rungt: int, runlt: int) -> bool:
    """检查ID是否符合过滤条件"""
    # 处理范围条件优先
    if rungt != 0 and runlt != 0:  # 同时指定了大于和小于条件
        range_match = (rungt < id < runlt)
    elif rungt != 0:  # 只指定了大于条件
        range_match = (id > rungt)
    elif runlt != 0:  # 只指定了小于条件
        range_match = (id < runlt)
    else:  # 没有指定范围条件
        range_match = True
    
    # 处理等于条件
    if isinstance(runeq, list):
        if len(runeq) == 0:  # runeq 为空列表，匹配所有 ID
            equal_match = True
        else:  # runeq 包含元素，只匹配列表中的 ID
            equal_match = (id in runeq)
    else:  # 向后兼容，处理旧的单数值情况
        if runeq != 0:
            equal_match = (id == runeq)
        else:
            equal_match = True
    
    # 综合判断：必须同时满足范围条件和等于条件
    match = range_match and equal_match
    return match

def get_web3_connection(url: str, max_retries: int = 3) -> Optional[Web3]:
    """获取Web3连接，带重试机制"""
    for attempt in range(max_retries):
        try:
            web3_obj = Web3(Web3.HTTPProvider(url))
            if web3_obj.is_connected():
                logger.info(f"成功连接到节点: {url}")
                return web3_obj
            else:
                logger.warning(f"第 {attempt+1} 次连接失败: {url}")
        except Exception as e:
            logger.error(f"第 {attempt+1} 次连接尝试异常: {e}")
        
        if attempt < max_retries - 1:
            time.sleep(2)  # 重试前等待
    
    logger.error(f"无法连接到节点: {url}，已尝试 {max_retries} 次")
    return None

def format_token_amount(amount: int, decimals: int) -> str:
    """格式化代币数量"""
    result = amount / (10 ** decimals)
    # 避免科学计数法显示，保留适当的小数位数
    formatted = f"{result:.{decimals}f}".rstrip('0').rstrip('.')
    # 如果结果太小接近于0，直接返回0
    if float(formatted) == 0 and result != 0:
        formatted = f"< 0.{'0' * (decimals - 1)}1"
    return formatted

def generate_privkey(name: str) -> None:
    """生成私钥"""
    while True:
        try:
            enter_count = [
                inquirer.Text('count', message="👉 输入账户数量")
            ]
            count = int(inquirer.prompt(enter_count, raise_keyboard_interrupt=True)['count'])
            if count > 0:
                break
            else:
                logger.info("❌  请输入正数.\n")
        except ValueError:
            logger.info("❌  请输入一个数字.\n")
    
    wallet_manager = WalletManager(name)
    
    for id in range(count):
        acct = Account.create()
        private_key = acct.key.hex()
        wallet_manager.add_private_key(private_key)
        logger.info(f"id: {id+1} privatekey: {private_key}")
    
    logger.success(f"批量生成 {count} 钱包私钥 -> {wallet_manager.get_wallets_filename()}")

def generate_address(name: str) -> None:
    """生成地址"""
    wallet_manager = WalletManager(name)
    wallets = wallet_manager.load_wallets()
    
    if not wallets:
        logger.warning(f"没有找到钱包数据: {wallet_manager.get_wallets_filename()}")
        return
    
    count = len(wallets)
    updated_wallets = wallets[:]  # 创建副本进行修改
    
    for idx, wallet_data in enumerate(wallets):
        id = idx + 1
        logger.debug(f"id: {id} data: {wallet_data}")
        
        # 检查是否已经有地址信息
        parts = wallet_data.split(',')
        if len(parts) == 2:
            continue  # 已有地址信息，跳过
        
        private_key = parts[0]
        address = get_address_by_key(private_key)
        
        if address:
            updated_wallets = wallet_manager.update_wallet_with_address(updated_wallets, private_key, address)
            logger.info(f"id: {id} address: {address}")
        else:
            logger.error(f"id: {id} 无法从私钥计算地址")
    
    # 保存更新后的钱包数据
    wallet_manager.save_wallets(updated_wallets)
    logger.success(f"批量计算 {count} 钱包地址 -> {wallet_manager.get_wallets_filename()}")

def generate_network_balance(name: str, runeq: List[int], rungt: int, runlt: int, network: str) -> None:
    """查询指定网络的余额"""
    wallet_manager = WalletManager(name)
    wallets = wallet_manager.load_wallets()
    
    if not wallets:
        logger.warning(f"没有找到钱包数据: {wallet_manager.get_wallets_filename()}")
        return
    
    # 获取网络配置
    if network not in NETWORK_CONFIG:
        logger.error(f"不支持的网络: {network}")
        return
    
    config = NETWORK_CONFIG[network]
    native_symbol = config["native_symbol"]
    native_decimals = config["native_decimals"]
    native_url = config["native_url"]
    token_address = config["token_contract"]
    
    # 连接到网络
    web3_obj = get_web3_connection(native_url)
    if not web3_obj:
        logger.error(f"无法连接到 {network} 网络: {native_url}")
        return
    
    try:
        # 获取Token合约实例
        token_address_checksum = Web3.to_checksum_address(token_address)
        token_contract = web3_obj.eth.contract(address=token_address_checksum, abi=CONTRACT_ABI_TOKEN)
        token_symbol = token_contract.functions.symbol().call()  # 获取代币符号
        token_decimals = token_contract.functions.decimals().call()  # 获取代币小数位数
    except Exception as e:
        logger.error(f"获取代币合约信息失败: {e}")
        return
    
    calc_count = 0
    for idx, wallet_data in enumerate(wallets):
        idx += 1
        if not is_id_valid(idx, runeq, rungt, runlt):
            continue
        
        calc_count += 1
        parts = wallet_data.split(',')
        private_key = parts[0] if len(parts) >= 1 else wallet_data
        
        address = get_address_by_key(private_key)
        if not address:
            logger.error(f"id: {idx} 无法从私钥计算地址: {private_key}")
            continue

        try:
            # 查询原生代币余额
            balance_native_raw = web3_obj.eth.get_balance(address)
            balance_native = format_token_amount(balance_native_raw, native_decimals)
            
            # 查询Token代币余额
            balance_token_raw = token_contract.functions.balanceOf(address).call()
            balance_token = format_token_amount(balance_token_raw, token_decimals)
            
            logger.info(f"id: {idx} address: {address} balance: {balance_native} {native_symbol} / {balance_token} {token_symbol}")
        except Exception as e:
            logger.error(f"id: {idx} 查询余额失败: {str(e)}")
        
        # 延迟，避免请求过于频繁
        delay = random.uniform(1, 3)
        time.sleep(delay)
    
    logger.success(f"批量查询 {calc_count} 个钱包 {config['native_name']} ({network.upper()}) 链余额 -> {wallet_manager.get_wallets_filename()}")


def choose_name() -> str:
    """选择钱包文件"""
    wallet_manager = WalletManager()
    existing_files = wallet_manager.scan_wallet_files()
    
    if existing_files:
        choices = [Choice(f"📁 {file}", file.replace('wallets-', '').replace('.txt', '') if file.startswith('wallets-') and file.endswith('.txt') else (file.replace('.txt', '') if file.endswith('.txt') else file)) for file in existing_files]
        choices.append(Choice("🆕 input", "input"))
        
        selected = select(
            '选择钱包文件',
            choices=choices,
            use_shortcuts=True,
            use_arrow_keys=True,
        ).ask()
        
        if selected == "input":
            enter_name = [
                inquirer.Text('name', message="👉 输入新钱包文件名")
            ]
            name = inquirer.prompt(enter_name, raise_keyboard_interrupt=True)['name']
        else:
            name = selected
    else:
        enter_name = [
            inquirer.Text('name', message="👉 输入新钱包文件名")
        ]
        name = inquirer.prompt(enter_name, raise_keyboard_interrupt=True)['name']
    
    return name


def main():
    # 初始化参数
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', type=bool, default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument('-e', '--equal', nargs='+', type=int, default=[])
    parser.add_argument('-g', '--greater', type=int, default=0)
    parser.add_argument('-l', '--less', type=int, default=0)
    args = parser.parse_args()
    run_debug = bool(args.debug)
    run_eq = list(args.equal)
    run_gt = int(args.greater)
    run_lt = int(args.less)
    
    # 日志级别
    log_level = "DEBUG" if run_debug else "INFO"
    logger.remove()
    logger.add(sys.stdout, level=log_level)

    try:
        while True:
            if platform.system().lower() == 'windows':
                os.system("title main")
            
            # 一级菜单
            answer = select(
                '选择功能',
                choices=[
                    Choice("🔥 批量生成ETH私钥", 'generate_privkey', shortcut_key="1"),
                    Choice("🔥 批量计算ETH地址", 'generate_address', shortcut_key="2"),
                    Choice("💰 批量查询链上余额", 'query_balance',    shortcut_key="3"),
                    Choice('❌ 退出', "exit", shortcut_key="0")
                ],
                use_shortcuts=True,
                use_arrow_keys=True,
            ).ask()
            
            if answer == 'generate_privkey':
                name = choose_name()
                generate_privkey(name)
            elif answer == 'generate_address':
                name = choose_name()
                generate_address(name)
            elif answer == 'query_balance':
                # 二级菜单
                network_choice = select(
                    '选择网络',
                    choices=[Choice(config['native_name'], network) for network, config in NETWORK_CONFIG.items()],
                    use_shortcuts=True,
                    use_arrow_keys=True,
                ).ask()
                
                if network_choice:
                    name = choose_name()
                    generate_network_balance(name, run_eq, run_gt, run_lt, network_choice)
            elif answer == 'exit':
                sys.exit()
    except KeyboardInterrupt:
        cprint(f'\n 退出，请按<Ctrl + C>', color='light_yellow')
        sys.exit()


if __name__ == '__main__':
    main()