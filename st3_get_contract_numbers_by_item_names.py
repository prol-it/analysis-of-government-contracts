'''
Период выборки указывается между start_date и end_date
Скрипт парсит данные по указанным наименованиям позиций в файле file_input
Формат файла file_input:
Наименование позиции (запишется в file_output); Далее чепрез символ ';' записывается семантическое ядро данной позиции
Например:
яйц;яйц;яйца;яйцо
Результат записывается в файлы file_output_название_обработанной_позиции
'''

import requests
from bs4 import BeautifulSoup
import csv
import os
import time
import sqlite3 as sq
from lib_gz import data_path, convert_str, file_db

start_date = '01.01.2017'
end_date = '31.12.2022'
file_input = data_path + 'products.csv'


def get_rows(name_pos, num_page):
    searchString = lambda: '' if len(name_pos) == 0 else 'searchString=' + name_pos + '&'

    url1 = 'https://zakupki.gov.ru/epz/contract/search/results.html?' + searchString()
    url2 = ''' 
    morphology=on&
    fz44=on&
    contractStageList_1=on&
    contractStageList_2=on&
    contractStageList=1%2C2&
    selectedContractDataChanges=ANY&
    contractCurrencyID=-1&
    budgetLevelsIdNameHidden=%7B%7D&
    customerPlace=5277347&
    executionDateStart=''' + start_date + '''&
    executionDateEnd=''' + end_date + '''&
    countryRegIdNameHidden=%7B%7D&
    sortBy=UPDATE_DATE&
    pageNumber=''' + str(num_page) + '''&
    sortDirection=false&
    recordsPerPage=_500&
    showLotsInfoHidden=false'''

    url2 = url2.replace('\n', '')
    url = url1 + ''.join(url2.split())

    HEADERS = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36'
    }

    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, 'html.parser')
    rows = soup.find_all('div', class_='row no-gutters registry-entry__form mr-0')

    return rows


if __name__ == "__main__":

    # Открываем файл file_input, считываем продукты в список
    list_products = []
    with open(file_input, 'r') as file:
        for i in file:
            list_products.append(i[:-1])

    # Парсим контракты, содержащие данные продукты
    for find_text in list_products:

        products = find_text.split(',')
        for product in products:

            num_page = 1
            sum_row = 0
            list_contracts = []

            # Получаем коллекцию BeautifulSoup согласно заданным параметрам
            rows = get_rows(product, num_page)

            while len(rows) > 0:
                print('Page', num_page, product)
                for item in rows:
                    # Номер контракта
                    contract_num = item.find('a').text.strip()[2:]
                    # Год исполнения контракта
                    contract_year_complite = item.find_all('div', class_='data-block__value')[1].text.strip()[-4::]
                    # Список позиций контракта
                    contract_list_products = item.find('span', class_='pl-0 col').find('a')
                    # Заказчик
                    contract_customer = convert_str(item.find('div', class_='registry-entry__body-href').text.strip())

                    # Если данный контракт содержит электронную версию, и контракта нет в списке, то сохраняем его
                    if contract_list_products is not None:
                        contract_exist = 0
                        for i in list_contracts:
                            if contract_num in i:
                                contract_exist = 1
                        if contract_exist == 0:
                            list_contracts.append(
                                contract_num + ';' + contract_year_complite + ';' + find_text + ';' + contract_customer)
                            sum_row += 1

                # Листаем страницы
                print('Total row =', sum_row)
                num_page = num_page + 1
                rows = get_rows(product, num_page)
                time.sleep(5)

            # Записываем результат в файл
            file_output = data_path + 'list_products_in_contracts_' + product + '_from_' + start_date + '_to_' + end_date + '_rows_' + str(
                sum_row) + '.csv'
            with open(file_output, 'a', newline='') as file:
                writer = csv.writer(file, delimiter='\n')
                writer.writerow(list_contracts)

    '''
    Заходит в папку <data_path> текущего проекта, берет все файлы *.csv и конкотинирует их в файл all.csv
    Заполняет этими данными таблицу products_in_contracts в БД gz.sqlite3 (file_db)
    '''

    # Заходит в папку <data_path> текущего проекта, берет все файлы *.csv и конкотинирует их в файл all.csv
    file_output = data_path + 'all.csv'

    with open(file_output, 'w') as f:
        for adress, dirs, files in os.walk(data_path):
            for file in files:
                if file == 'products.csv':
                    continue
                full_path = os.path.join(adress, file)
                if full_path[-4:] == '.csv':
                    f.write(open(full_path).read())

    # Заполняет данными таблицу products_in_contracts в БД gz.sqlite3 (file_db) из исходного файла file_output

    # Открываем файл и для начала выводим справочную информацию по нему
    set_product = set()
    set_contract = set()
    set_contract_year = set()
    set_contract_year_customer = set()
    set_contract_year_product_customer = set()

    with open(file_output, 'r') as file:
        count = 1
        for row in file:
            count += 1
            contract, year, product, customer = row[:-1].split(';')
            set_product.add(product)
            set_contract.add(contract)
            set_contract_year.add(contract + ';' + year)
            set_contract_year_customer.add(contract + ';' + year + ';' + customer)
            set_contract_year_product_customer.add(contract + ';' + year + ';' + product + ';' + customer)

    os.remove(file_output)
    print('Количество продуктов:', len(set_product))
    print('Количество контрактов:', len(set_contract))
    print('Контракт/год:', len(set_contract_year))
    print('Контракт/год/заказчик:', len(set_contract_year_customer))
    print('Контракт/год/продукт/заказчик:', len(set_contract_year_product_customer))


    # Заполняем список кортежей данными из множества
    data = []
    for row in set_contract_year_product_customer:
        contract, year, product, customer = row.split(';')
        data.append((contract, year, product, customer, 1))

    with sq.connect(file_db) as con:
        cur = con.cursor()

        cur.execute('DROP table if exists products_in_contracts')
        con.commit()

        # Создаем таблицу
        cur.execute('''
            CREATE TABLE products_in_contracts (
                contract TEXT,
                year INTEGER,
                find_text TEXT,
                customer TEXT,
                in_work INTEGER
            )
        ''')

        # Заполняем таблицу из списка кортежей
        cur.executemany(
            'INSERT INTO products_in_contracts (contract, year, find_text, customer, in_work) VALUES (?, ?, ?, ?, ?)',
            data)
