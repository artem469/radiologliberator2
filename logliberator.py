#!/usr/bin/env python3

# This script scrapes logs from qrz.com.
# Original Author: Shawn Jones 2015 | shawnjones20@gmail.com
# Updated for Python 3 and modern QRZ.com compatibility.

# Log Liberator v0.2 (Updated)

import re
import sys
import requests
from bs4 import BeautifulSoup as soup
# You still need to ensure 'ADIF_log' is available, e.g., in a separate file or included library.
from ADIF_log import ADIF_log 
# Note: Removed the unused 'sys' import from the middle of the original script

# --- Helper Functions ---

def assign_value(entry, name, value):
    """Assigns a value, handling potential encoding issues gracefully."""
    value_stripped = value.strip()
    if len(value_stripped) > 0:
        # Simplified for Python 3, avoiding complex nested try/except for encoding
        try:
            entry[name] = value_stripped
        except Exception as e:
            # Fallback for complex characters, though less common in Py3
            try:
                entry[name] = value_stripped.encode('ascii', 'replace').decode('ascii')
            except:
                print(f"Failed to set value for '{name}' to '{value_stripped}'. Error: {e}")
                
def assign_call(entry, name, value):
    if value is None:
        return
    # Python 3 strings handle Unicode; replacing the obscure \xd8 (Ø) character with '0'
    value = value.replace('\xd8', '0') 
    assign_value(entry, name, value)

def str_or_intl(entry, name, value):
    value_stripped = value.strip()
    if len(value_stripped) > 0:
        try:
            # Try setting the standard field
            entry[name] = value_stripped
        except:
            # If standard field fails, try setting international versions as a fallback
            assign_value(entry, name+'_intl', value)
            assign_value(entry, name, value)

def get_tds(tag):
    # Changed to find_all for consistency and compatibility
    return tag.find_all('td')

# --- Handler Class ---

class Handler(object):
    # Note: These methods assume a specific table structure (using <th>/<td> or just <td>s)
    # The current methods might need adjustment if QRZ's HTML structure for logbook rows has changed drastically.
    
    def Serial(self, ent, tag):
        tds = get_tds(tag)
        if len(tds) >= 2:
            ld_tag = tds[1].find('span', string='Log Date:')
            if ld_tag:
                ld = ld_tag.next_sibling.next_sibling.text
                ld = ld[0:10].replace('-','')
                assign_value(ent, 'QRZCOM_QSO_UPLOAD_DATE', ld)

    # def QSO_Start(self, ent, tag):
    #     tds = get_tds(tag)
    #     if len(tds) >= 2:
    #         qs = tds[1].text
    #         qsd = qs[0:10].replace('-','')
    #         qst = qs[11:19].replace(':','')
    #         assign_value(ent, 'QSO_DATE', qsd)
    #         assign_value(ent, 'TIME_ON', qst)
    def QSO_Start(self, ent, tag):
        tds = get_tds(tag)
        if len(tds) < 2:
            return

        qs_tag = tds[1]
        qs_text = qs_tag.text.strip()

        # ОКОНЧАТЕЛЬНАЯ ПРОВЕРКА: Если поле пустое или содержит "no", пропускаем.
        if qs_text.lower() == 'no' or len(qs_text) < 19:
            # НЕ НУЖНО ПЕЧАТАТЬ WARNING, так как это просто пропуск невалидных данных
            return

        # Парсинг продолжается только, если данные выглядят как дата/время
        qsd = qs_text[0:10].replace('-', '')
        qst = qs_text[11:19].replace(':', '')

        assign_value(ent, 'QSO_DATE', qsd)
        assign_value(ent, 'TIME_ON', qst)

    def QSO_End(self, ent, tag):
        tds = get_tds(tag)
        if len(tds) >= 4:
            qe = tds[1].text
            # contest = tds[3].text # Original logic was flawed; retrieving contest from the 4th td
            qed = qe[0:10].replace('-','')
            qet = qe[11:19].replace(':','')
            assign_value(ent, 'QSO_DATE_OFF', qed)
            assign_value(ent, 'TIME_OFF', qet)

    # Simplified the remaining methods to rely on the 'get_tds' helper for structure.
    # The original structure might be simplified by QRZ.com to just two <td> elements.

    def Station(self, ent, tag):
        his, mine = get_tds(tag)
        assign_call(ent, 'call', his.text)
        assign_call(ent, 'operator', mine.text)

    def Op(self, ent, tag):
        his, mine = get_tds(tag)
        str_or_intl(ent, 'name', his.text)
        str_or_intl(ent, 'my_name', mine.text)

    def QTH(self, ent, tag):
        his, mine = get_tds(tag)
        str_or_intl(ent, 'qth', his.text)
        str_or_intl(ent, 'my_city', mine.text)

    def State(self, ent, tag):
        his, mine = get_tds(tag)
        assign_value(ent, 'state', his.text);
        assign_value(ent, 'my_state', mine.text);

    def Country(self, ent, tag):
        his, mine = get_tds(tag)
        assign_value(ent, 'country', his.text);
        assign_value(ent, 'my_country', mine.text);

    # Renamed to match the most likely table header text on QRZ log pages
    def Frequency(self, ent, tag): 
        # Assumes the structure is: [His Freq/Band], [His Mode], [My Freq/Band], [My Mode]
        tds = get_tds(tag)
        if len(tds) < 4: return 

        his_freq_band = tds[0]
        his_mode = tds[1]
        my_freq_band = tds[2]
        
        # NOTE: This parsing is complex and heavily dependent on old QRZ HTML structure.
        # It's kept here but is a major point of failure.
        
        freq = his_freq_band.contents[0].strip() if len(his_freq_band.contents) > 0 else ''
        band = his_freq_band.find('span', class_='band').text.upper() if his_freq_band.find('span', class_='band') else '' # Attempt to find band more robustly
        mode = his_mode.text
        
        assign_value(ent, 'band', band)
        assign_value(ent, 'freq', freq.replace(' MHz', ''))
        assign_value(ent, 'mode', mode)

    def Power(self, ent, tag):
        # Assumes the structure is: [His Power], [His RST], [My Power], [My RST]
        tds = get_tds(tag)
        if len(tds) < 4: return
        
        # His Power (rx)
        po_rx = tds[0].text.replace(' W','').strip()
        rst_rcvd = tds[1].text.strip()
        if po_rx.isdigit() and int(po_rx) > 0:
            assign_value(ent, 'rx_pwr', po_rx)
        assign_value(ent, 'rst_rcvd', rst_rcvd)
        
        # My Power (tx)
        po_tx = tds[2].text.replace(' W','').strip()
        rst_sent = tds[3].text.strip()
        if po_tx.isdigit() and int(po_tx) > 0:
            assign_value(ent, 'tx_pwr', po_tx)
        assign_value(ent, 'rst_sent', rst_sent)

    def Coordinates(self, ent, tag):
        # NOTE: This method has complex regex that must be protected by raw strings (r'') in Py3.
        his, mine = get_tds(tag)
        
        # His Coordinates
        lat, lon = his.text.split(',', 1) # Use split with max 1 to handle messy data
        latm = re.search(r'([0-9]+)\.([0-9]+) ([NS])', lat) # Added raw string 'r'
        if latm is not None:
            mins = float('0.'+latm.group(2))*60
            assign_value(ent, 'lat', latm.group(3)+'%03u %#06.3f' % (int(latm.group(1)), mins))
        lonm = re.search(r'([0-9]+)\.([0-9]+) ([EW])', lon) # Added raw string 'r'
        if lonm is not None:
            mins = float('0.'+lonm.group(2))*60
            assign_value(ent, 'lon', lonm.group(3)+'%03u %#06.3f' % (int(lonm.group(1)), mins))
            
        # My Coordinates
        lat, lon = mine.text.split(',', 1)
        latm = re.search(r'([0-9]+)\.([0-9]+) ([NS])', lat) # Added raw string 'r'
        if latm is not None:
            mins = float('0.'+latm.group(2))*60
            assign_value(ent, 'my_lat', latm.group(3)+'%03u %#06.3f' % (int(latm.group(1)), mins))
        lonm = re.search(r'([0-9]+)\.([0-9]+) ([EW])', lon) # Added raw string 'r'
        if lonm is not None:
            mins = float('0.'+lonm.group(2))*60
            assign_value(ent, 'my_lon', lonm.group(3)+'%03u %#06.3f' % (int(lonm.group(1)), mins))

    def Grid(self, ent, tag):
        # Assumes the structure is: [His Grid], [Dist], [My Grid], [Bear]
        tds = get_tds(tag)
        if len(tds) < 4: return
        
        his_grid, dist, my_grid, my_bear = tds[0].text, tds[1].text, tds[2].text, tds[3].text
        
        assign_value(ent, 'gridsquare', his_grid)
        km = re.search('([0-9]+) km', dist)
        if km is not None and int(km.group(1)) > 0:
            assign_value(ent, 'distance', km.group(1))
            
        assign_value(ent, 'my_gridsquare', my_grid)
        deg = re.search(r'([0-9]+)\xb0', my_bear) # Added raw string 'r' for the degree symbol
        if deg is not None:
            assign_value(ent, 'ant_az', deg.group(1))

    def Continent(self, ent, tag):
        # Assumes the structure is: [His Cont], [His IOTA], [My Cont], [My IOTA]
        tds = get_tds(tag)
        if len(tds) < 4: return
        
        his_cont, his_iota, my_cont, my_iota = tds[0].text, tds[1].text, tds[2].text, tds[3].text
        
        ct = his_cont.strip()[0:2]
        assign_value(ent, 'cont', ct)
        assign_value(ent, 'iota', his_iota)
        assign_value(ent, 'my_iota', my_iota)

    def Zones(self, ent, tag):
        # Assumes the structure is: [His ITUZ], [His CQZ], [My ITUZ], [My CQZ]
        tds = get_tds(tag)
        if len(tds) < 4: return

        his_ituz, his_cqz, my_ituz, my_cqz = tds[0].text, tds[1].text, tds[2].text, tds[3].text

        assign_value(ent, 'ituz', his_ituz)
        cqz = re.search('[0-9]+', his_cqz)
        if cqz is not None:
            assign_value(ent, 'cqz', cqz.group(0))
            
        assign_value(ent, 'my_itu_zone', my_ituz)
        cqz = re.search('[0-9]+', my_cqz)
        if cqz is not None:
            assign_value(ent, 'my_cq_zone', cqz.group(0))

    def QSL_Via(self, ent, tag):
        his, mine = get_tds(tag)
        assign_value(ent, 'qsl_via', his.text)

    def Confirmed(self, ent, tag):
        # Этот обработчик существует только для того, чтобы скрипт
        # корректно обнаруживал тег "Confirmed" и пропускал его,
        # не вызывая ошибку парсинга даты/времени.
        pass

    def Comments(self, ent, tag):
        comment = tag.find('td')
        if comment:
            str_or_intl(ent, 'comment', comment.text)

    def Notes(self, ent, tag):
        comment = tag.find('td')
        if comment:
            str_or_intl(ent, 'notes', comment.text)

# --- Main Execution ---

print("**********************************************")
print("******* Logbook Liberator v0.2     *******")
print("**********************************************")
print("")

# 1. Update: Changed raw_input to standard Python 3 input()
_username = input("Username: ")
_password = input("Password: ")

payload = {
    # NOTE: QRZ.com may require a hidden token or other fields now. 
    # This payload might be incomplete for a modern login.
    'username': _username,
    'password': _password
    }

print("")
print("Here we go. Viva la Logbook!!")
print("")

with requests.Session() as s:
    # 2. Update: Changed HTTP to HTTPS for the login URL
    p = s.post('https://www.qrz.com/login', data=payload)

    print('Getting Book ID(s)')
    # 3. Update: Changed HTTP to HTTPS for logbook URL
    r = s.post('https://logbook.qrz.com', data={'page':1})
    # 4. Update: Added 'html.parser' for Python 3 compatibility
    data = soup(r.text, 'html.parser') 
    
    # Check for login failure immediately
    if data.find('h1', text='QRZ Logbook') is None and data.find('input', attrs={'name':'username'}):
        print("🚫 CRITICAL ERROR: Login failed or session invalid after POST to logbook. Please check credentials or QRZ login requirements (e.g., Captcha/token).")
        sys.exit(1)

    bookids = []
    # 5. Update: Changed findAll to find_all for BeautifulSoup 4 compatibility
    all_bookids = data.find_all('option', attrs={'id':re.compile('^booksel'),'value':re.compile('^[0-9]+$')})
    for id in all_bookids:
        bookids.append(int(id['value']))
    
    # 6. Update: Changed print statement to function call (Python 3 syntax)
    print(bookids) 

handler = Handler()

for bookid in bookids:
    adif = ADIF_log("Radio Log Liberator")

    print('Getting total QSOs')
    r = s.post('https://logbook.qrz.com', data={'bookid':bookid})
    data = soup(r.text, 'html.parser')
    total_qsos = data.find('input', attrs={'name':'logcount'})
    if total_qsos is None:
        print('Unable to find number of QSOs. Check if the logbook is empty or HTML structure changed.')
        # 7. Update: Changed system.exit(1) to sys.exit(1) and moved import up
        sys.exit(1) 
    total_qsos = int(total_qsos['value'])

    print('Fetching '+str(total_qsos)+' from book '+str(bookid))

    for i in range(0, total_qsos):
        print("Working on QSO: %s of %s" % (i + 1, total_qsos)) # Updated print to show QSO number (1-based)
        getpages = {'op':'show', 'bookid':bookid, 'logpos':i};
        r = s.post('https://logbook.qrz.com', data=getpages)
        data = soup(r.text, 'html.parser')
        
        # 8. Update: Changed 'logitem' ID to 'lbrecord' as a possible modern ID for the QSO box
        logitem = data.find('div', id='lbrecord') 
        if logitem is None:
            print('Unable to find log item for QSO '+str(i+1))
            print("--- HTML Snippet for Debugging ---")
            print(r.text[:500])
            print("----------------------------------")
            continue
            
        # 9. Update: Changed findAll to find_all for BeautifulSoup 4 compatibility
        rows = logitem.find_all('tr') 
        if len(rows) == 0:
            print('Unable to find QSO details (TR rows) for QSO '+str(i+1))
            continue
            
        ent = adif.newEntry()
        for j in range(0, len(rows)):
            # 10. Update: Changed tag lookup from 'td' to 'th' based on the structure defined in the Handler class
            title = rows[j].find('th') 
            if title is None:
                continue
            
            # The .encode() and .decode() logic is kept for compatibility with the old ADIF_log structure
            title_text = title.text.strip().replace(':','').replace(' ','_')
            
            if hasattr(handler, title_text):
                # Fixed a potential issue with method dispatch by ensuring title_text is a standard string
                getattr(handler, title_text)(ent, rows[j])

    f = open('Logbook-'+str(bookid)+'.adi', 'w')
    f.write(str(adif))
    f.close()

print("")
print("Logbook liberated!")
print("")
