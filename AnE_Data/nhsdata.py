import requests, bs4, os
import pandas as pd
import numpy as np
from time import strptime

ane_root_url = "https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/"

month_names = ["January", "February","March", "April","May", "June", "July",
          "August", "September", "October", "November", "December"]

########################################################################################
################################# Getting spreadsheets #################################
########################################################################################

def getAnEpages(url = ane_root_url, verbose = 0):
    '''
    Gets the urls of the monthly and weekly A&E data pages from the specified URL
    '''
    
    res = requests.get(url)
    soup = bs4.BeautifulSoup(res.content, features="lxml")

    linkElems = soup.select("a")
    page_names = []

    for elem in linkElems:
        if "Monthly A&E Attendances and Emergency Admissions" in elem.getText():
            page_names.append(elem.get('href'))
        elif "Weekly A&E Attendances and Emergency Admissions" in elem.getText():
            page_names.append(elem.get('href'))

    if verbose >= 10:
        print("Total of {} pages found".format(len(page_names)))
        
    return page_names

def get_xls_files(pages, verbose = 0):
    '''
    Collects the names of the relevent xls files from the given list of webpages
    '''
    xls_file_names = []

    for name in pages:
        #print("Looking at page: ", name, '\n')
        res = requests.get(name)
        soup = bs4.BeautifulSoup(res.content, features="lxml")
        linkElems = soup.select("a")
        for elem in linkElems:
            if 'AE' in elem.get('href') and '.xls' in elem.get('href'):
                xls_file_names.append(elem.get('href'))
                #print(elem.get('href'))
            elif 'by-provider' in elem.get('href') and '.xls' in elem.get('href'):
                # To account for the change in January 2020
                xls_file_names.append(elem.get('href'))
                
    if verbose >= 10:
        print("Total of {} xls files found.".format(len(xls_file_names)))
        
    return xls_file_names

def check_files(files, verbose = 0):
    '''
    Checks each file name in given list to check if the
    name contains any of the words from avoid_list
    which indicate that the file is not one of the 
    normal monthly datasets.

    Returns single Boolean.
    '''
    
    avoid_list = ["Quarter", "QUARTER", 
                  "Timeseries","Time-Series", 
                  "Q1","Q2","Q3","Q4",
                  "transparency"]   
    
    def check_file(name):
        '''
        Checks if the file name contains any of the words from avoid_list
        which indicate that the file is not one of the normal monthly datasets.

        Returns single Boolean.
        '''
        use = True
        for item in avoid_list:
            if item in name:
                   use = False
        return use 
    
    # Gather data that we actually want to use
    outFiles = []
    for i, name in enumerate(files):
        if check_file(name):
            outFiles.append(name)
    if verbose >= 10:
        print("Found {} data sets.".format(len(outFiles)))
        
    return outFiles

def get_all_names(latestSheet, verbose = 0):
    
    resp = requests.get(latestSheet)
    # Store the data in a temporary file
    tempfile = open('tempfile.xls', 'wb')
    tempfile.write(resp.content)
    tempfile.close()
    sheet = pd.read_excel('tempfile.xls', sheet_name=0, skiprows=15, usecols="A,B,C,D,E,F,G,H,I,J,K,L,M,N")

    currentNames = sheet["Name"].values

    oldTrusts = np.array(["Bedford Hospital NHS Trust", 
                          "Luton And Dunstable University Hospital NHS Foundation Trust",
                          "Basildon And Thurrock University Hospitals NHS Foundation Trust",
                          "Mid Essex Hospital Services NHS Trust",
                          "Southend University Hospital NHS Foundation Trust",
                          "Royal Liverpool And Broadgreen University Hospitals NHS Trust",
                          "Aintree University Hospital NHS Foundation Trust",
                          "Central Manchester University Hospitals NHS Foundation Trust",
                          "University Hospital Of South Manchester NHS Foundation Trust"])

    allNames = np.concatenate((currentNames, oldTrusts))
    os.remove("tempfile.xls")
    return allNames


############################################################################################
################################## Collecting the data #####################################
############################################################################################

def collectData(data, allNames, verbose = 0):
    
    def try1(sheet):
        try: over4hours = sheet["Total Attendances > 4 hours"][0]
        except: return False 
        return True

    def try2(sheet):
        try: over4hours = sheet["Total Attendances < 4 hours"][0]
        except: return False 
        return True

    def try3(sheet):
        try: over4hours = sheet["Percentage in 4 hours or less (all)"][0]
        except: return False 
        return True

    def makeDataMask(data):
        dataMask = np.zeros(len(data),dtype=bool)
        for c, cell in enumerate(data):
            if type(cell)==str or np.isnan(cell):
                dataMask[c]=False
            else:
                dataMask[c]=True
        return dataMask
    # Make vectorised int function
    vecint = np.vectorize(int)
    
    missing = []
    attendences2 = np.zeros((len(allNames), len(data)),dtype=object) 
    attendences2[:,:] = '-'
    over4hours = np.zeros((len(allNames), len(data)),dtype=object) 
    over4hours[:,:] = '-'
    periods2 = np.zeros(len(data),dtype = object)
    
    for i, name in enumerate(data):   
        # Get the data location
        resp = requests.get(name)

        # Store the data in a temporary file
        tempfile = open('tempfile.xls', 'wb')
        tempfile.write(resp.content)
        tempfile.close()

        # Get all of the data from row 16 with columns A to N
        # I don't think this is how try is supposed to be used but it works
        sheet = pd.read_excel('tempfile.xls', sheet_name=0, skiprows=15, usecols="A,B,C,D,E,F,G,H,I,J,K,L,M,N")
        sheetTest = sheet

        names = sheet['Name'].values  
        all_attendence = sheet["Total attendances"]

        # Get the total attendance
        try:
            attendence = sheet["Total attendances"][0]
        except:
            attendence = sheet["Total Attendances"][0]


        # Try each of the three attendance column headers
        if try1(sheet):
            #print(1)
            sample = sheet["Total Attendances > 4 hours"].values
            all_over4hours = np.zeros(len(sample),dtype=object)
            all_over4hours[:] = '-'
            mask = makeDataMask(sample)
            all_over4hours[mask] = sample[mask]
        elif try2(sheet):
            #print(2)
            sample = sheet["Total Attendances < 4 hours"].values
            all_over4hours = np.zeros(len(sample),dtype=object)
            all_over4hours[:] = '-'
            mask = makeDataMask(sample)
            all_over4hours[mask] = all_attendence.values[mask] - sample[mask]
        elif try3(sheet):
            #print(3)
            sample = sheet["Percentage in 4 hours or less (all)"].values
            all_over4hours = np.zeros(len(sample),dtype=object)
            all_over4hours[:] = '-'
            mask = makeDataMask(sample)
            all_over4hours[mask] = vecint((1-sample[mask])*all_attendence.values[mask])

        for j, fname in enumerate(allNames):
            if fname in names:
                # Save attendance data
                hospital_attendence = all_attendence[names==fname]
                attendences2[:,i][allNames==fname] = hospital_attendence

                # Save waiting data
                num_waiting = all_over4hours[names==fname]
                over4hours[:,i][allNames==fname] = num_waiting

            # Combine Luton + Dunst Hosp with Luton + Dunst *Uni* Hosp
            if "Luton And Dunstable Hospital NHS Foundation Trust" in names:
                hospital_attendence = all_attendence[names=="Luton And Dunstable Hospital NHS Foundation Trust"]
                attendences2[:,i][allNames=="Luton And Dunstable University Hospital NHS Foundation Trust"] = hospital_attendence

                # Save waiting data
                num_waiting = all_over4hours[names=="Luton And Dunstable Hospital NHS Foundation Trust"]
                over4hours[:,i][allNames=="Luton And Dunstable University Hospital NHS Foundation Trust"] = num_waiting

            else:
                #print("Error: {} not found".format(fname))
                pass

        # checking for missing names
        for test_name in names:
            if test_name not in allNames and test_name not in missing:
                #print("Error: {} has no home".format(test_name))
                missing.append(test_name)

        # Get cell containing the data period
        sheet = pd.read_excel('tempfile.xls', sheet_name=0, skiprows=5, usecols="C")
        period = sheet.columns[0]
        #print(period)
        periods2[i] = period

        if verbose == 0:
            print("{} complete of {}...".format(i+1,len(data)),end = "\r")
    
    os.remove("tempfile.xls")
    return attendences2, over4hours, periods2

########################################################################################
#################################### Sort out dates ####################################
########################################################################################

def convMonths(date):
    strip=strptime(date, "%B %Y")
    text = "{:02d}/{}".format(strip[1], strip[0])
    return text

def convPeriods(periods):
    # Make array of monthly data periods
    
    period_months = []
    for period in periods:
        # Check if it's month or week data
        month = False
        if period.split(' ')[0] in month_names:
            text = convMonths(period)
            period_months.append(text)
        else:
            text = period.split(' ')[2][3:]
            if text not in period_months:
                period_months.append(text)
    return period_months

def weekly2monthy(dates, weekly_data, printOutput = False):
    # It's "Week ending <date>" so for each week, if the day is less than 7 
    # I need to give a fraction to the previous month
    days = np.zeros(len(dates))
    months = np.zeros(len(dates))
    years = np.zeros(len(dates))
    
    for i,week in enumerate(dates):
        #print(week)
        split = week.split(' ')[2].split('/')
        days[i] = int(split[0])
        months[i] = int(split[1])
        years[i] = int(split[2])

    monthly_data = []
    weekly_data = np.asarray(weekly_data)
    
    new_dates = []
    for year in range(int(min(years)),int(max(years))+1):
        for month in range(1, 13):
            mask = (years==year)*(months==month)
            new_dates.append("{:02d}/{}".format(month, year))
            if sum(mask) > 0:
                # Find the data corresponding to this month
                month_data = weekly_data[mask]
                if '-' not in month_data:
                    week_ending = days[mask]

                    # Calculate how much of the data came from the previous month 
                    # if this isn't the first data point, give the data to that month
                    give_to_pevious = (7-week_ending[-1])*month_data[0]/7
                    if len(monthly_data) > 0 and monthly_data[-1]!='-':
                        monthly_data[-1] += give_to_pevious

                    # Calulate total for this month minus donated data
                    out = sum(month_data) - give_to_pevious
                    # Check that we have all of the data for this month and if we do, append to final data list
                    expected_data_entries = np.floor(abs(week_ending[0]-week_ending[-1])/7+1)
                    if not int(expected_data_entries) == len(month_data):
                        print("Error! Set: {} \n       Should be {} but it's {}.".format(np.asarray(dates)[mask], 
                                                        expected_data_entries, len(month_data)))
                        print("Set will not be included in final data.")
                    else:
                        
                        #print(month_data)
                        if 0 in month_data:
                            monthly_data.append('-')
                        else:
                            monthly_data.append(out)
                else:
                    monthly_data.append('-')


    return monthly_data, new_dates

def sort_data(allNames, data, unsorted_periods):
    periods = convPeriods(unsorted_periods)
    final_attendence = np.zeros((len(allNames), len(periods)), dtype=object)
    
    month_mask = [unsorted_periods[i].split(' ')[0] in month_names for i in range(len(unsorted_periods))]
    #print(month_mask)
    for i, row in enumerate(data):
        month_data = row[month_mask]
        weekly_data, blah = weekly2monthy(unsorted_periods[np.invert(month_mask)], row[np.invert(month_mask)])
        weekly_data = weekly_data[:-1]
        #print(blah[0], blah[-1], periods[0],periods[-1]) This proves that I need to flip the weekly data
        #print(type(month_data),type(weekly_data))
        final_attendence[i,:] = np.concatenate((month_data, weekly_data[::-1]))
        
    months = []
    for period in periods:
        year = float(period.split('/')[1])
        month = float(period.split('/')[0])
        months.append(year+month/12)
    months = np.asarray(months)
        
    return final_attendence, months


def tidy_data(data):
    #Delete the nan line
    if data[1,0] == "-":
        data = np.delete(data, 1, axis=0)

    for i in range(len(data[:,0])):
        for j in range(len(data[i,:])):
            if data[i,j] != '-':
                data[i,j] = int(float(data[i,j]))
    return data
            