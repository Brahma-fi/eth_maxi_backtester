import pandas as pd
import numpy as np
from datetime import timedelta

def ftxTransformer(data):
    data['endTime'] =  (pd.to_datetime(data['startTime'].copy())+timedelta(seconds =3600))
    data.drop(['Unnamed: 0','volume','startTime'],axis=1,inplace=True)
    cols = ['endTime','open','high','low','close']
    output_data = data[cols].copy()
    output_data.sort_values(by=['endTime'],inplace=True)
    output_data.set_index('endTime',inplace=True)
    
    weekly_data = output_data.resample('7d',offset = '8h',label='right').agg({'open':'first','close':'last','high':'max','low':'min'})
    
    # drop this as last week data is extrapolated
    weekly_data.drop(index = weekly_data.index[-1], 
        axis=0, 
        inplace=True)
    weekly_data['price_change'] = weekly_data['close'] / weekly_data['open']  - 1
    weekly_data = weekly_data.dropna()

    return output_data,weekly_data


def chainlinkTransformer(data):
    data['endTime'] =  (pd.to_datetime(data['updatedAt'].copy(),unit='s'))
    data.drop(['updatedAt','startedAt','roundId','roundId.1'],axis=1,inplace=True)
    data['price'] = data['price'].copy() / 1e8
    data.sort_values(by=['endTime'],inplace=True)
    data.set_index('endTime',inplace=True)
    data['index_twap'] = data.rolling('15min').mean()
    
    #generate weeklyData
    opens = data.price.resample('7d',offset = '8h',label='right').first()
    opens.rename('open',inplace=True)
    mins = data.index_twap.resample('7d',offset = '8h',label='right').min()
    mins.rename('low',inplace=True)
    maxs = data.index_twap.resample('7d',offset = '8h',label='right').max()
    maxs.rename('high',inplace=True)
    
    weekly_data = pd.concat([opens,maxs,mins],axis=1)
    weekly_data['close'] = weekly_data.open.shift(-1)
    weekly_data = weekly_data[['open','close','high','low']]
    # drop this as last week data is extrapolated
    weekly_data.drop(index = weekly_data.index[-1], 
            axis=0, 
            inplace=True)
    
    weekly_data['price_change'] = weekly_data['close'] / weekly_data['open']  - 1
    

    #generate hourlyData
    opens = data.price.resample('1h',offset = '8h',label='right').first()
    opens.rename('open',inplace=True)
    mins = data.index_twap.resample('1h',offset = '8h',label='right').min()
    mins.rename('low',inplace=True)
    maxs = data.index_twap.resample('1h',offset = '8h',label='right').max()
    maxs.rename('high',inplace=True)
    
    hourly_data = pd.concat([opens,maxs,mins],axis=1)
    hourly_data['close'] = hourly_data.open.shift(-1)
    hourly_data = hourly_data[['open','close','high','low']]
    # drop this as last week data is extrapolated
    hourly_data.drop(index = hourly_data.index[-1], 
            axis=0, 
            inplace=True)
    
    return data,weekly_data,hourly_data



def dvolTransformer(data):
    data['endTime'] = pd.to_datetime(data['date'].copy(),utc=True)
    data.set_index('endTime',inplace=True)
    data.drop(['date','high','low'],axis=1,inplace=True)
    data.rename(columns={'open':'dvol_open','close':'dvol_close'},inplace=True)
    hourly_data = data.copy()
    
    weekly_data = hourly_data.resample('7d',offset = '8h',label='right').agg({'dvol_open':'first','dvol_close':'last'})

    #drop last row which is interpolated
    weekly_data.drop(index = weekly_data.index[-1], 
        axis=0, 
        inplace=True)


    return hourly_data,weekly_data


def skewDataTransformer(data):
    data['endTime'] = pd.to_datetime(data['DateTime'].copy(),utc=True,format='%d/%m/%Y %H:%M' )
    data.set_index('endTime',inplace=True)
    data.drop(['DateTime'],axis=1,inplace=True)
    data.rename(columns={'1wk ATM Vol':'open'},inplace=True)
    data['close'] = data.open.shift(-1).fillna(method='ffill') 
    hourly_data = data.copy()
    
    weekly_data = hourly_data.resample('7d',offset = '8h',label='right').agg({'open':'first','close':'last'})

    #drop last row which is interpolated
    weekly_data.drop(index = weekly_data.index[-1], 
        axis=0, 
        inplace=True)


    return hourly_data, weekly_data



def create_moving_avg(hourly_data,weekly_data,ma_window):
    """
    Creates simple moving average for a weekly dataframe using hourly inputs and window length
    
    weekly_data is DataFrame with DateIndex where dates are the week end dates
    hourly_data is DataFrame with DateIndex
    ma_window is a string
    """
    
    # Need MA at the weeks start date.
    # E.g. for endDate 2021-04-09, need the MA for the window preceding 2021-04-02.
    # Daily Moving Avg is therefore shifted 8days to align correctly.
    daily_data = hourly_data.close.resample('1d',offset = '8h',label='right').last()

    ma = daily_data.rolling(ma_window).mean().rename('moving_avg').shift(8)
    
    moving_avg = ma[weekly_data.index].copy()
    
    return moving_avg

def create_realised_vol(hourly_data,weekly_data, rv_window):
    """
    Creates realised volatiltiy for a weekly dataframe using hourly inputs and window length
    
    weekly_data is DataFrame with DateIndex where dates are the week end dates
    hourly_data is DataFrame with DateIndex
    rv_window is a string
    """
    
    daily_data = hourly_data.close.resample('1d',offset = '8h',label='right').last()

    realised_vol = (np.log(1+daily_data.pct_change()).rolling(rv_window).std()*np.sqrt(365)).rename('realised_volatilty')

    # weekly_data DateIndex are week end dates so realised_vol is for window preceding end date.
    rv_end = realised_vol[weekly_data.index]
    
    # shift rv to get realised volatility for window preceding the weeks start date
    rv_start = rv_end.shift()
    
    return rv_start,rv_end


def lyraDuneProcessingHistoricalIV(base_iv_files, skew_files):
    """
    Function to process raw Lyra Historical IV history data from Dune
    Inputs are string paths to two csv file downloads from Dune
    baseIV_file is downloaded from https://dune.xyz/queries/470814 
    skew_file is downloaded from https://dune.xyz/queries/547201
    
    Output is dictionary where keys are expiry date and values are
    DataFrames containing the hourly IV for each strike listed    
    """
    base_iv = pd.DataFrame()
    skew = pd.DataFrame()
    
    if not isinstance(base_iv_files, str):
        for base_file in base_iv_files:
            base_iv = pd.concat([base_iv,pd.read_csv(base_file)])
        for skew_file in skew_files:
            skew = pd.concat([skew,pd.read_csv(skew_file)])
    else:
        base_iv = pd.read_csv(base_iv_files)
        skew = pd.read_csv(skew_files)
    
    base_iv['date'] = pd.to_datetime(base_iv['evt_block_time'])
    base_iv.drop(['evt_block_time'],axis=1,inplace=True)
    base_iv.set_index('date',inplace=True)
    base_iv.sort_index(inplace=True)    

    skew['date'] = pd.to_datetime(skew['evt_block_time'])
    skew.drop(['evt_block_time'],axis=1,inplace=True)
    skew.set_index('date',inplace=True)
    skew.sort_index(inplace=True)
    
    expiries = np.sort( base_iv.expiry.drop_duplicates() )
    
    lyra_skews = {}
    for expiry in expiries:
      
        current_skew = skew[skew.expiry==expiry]
        
        current_base_iv = base_iv[base_iv.expiry==expiry]
        current_base_iv = current_base_iv[~current_base_iv.index.duplicated(keep='last')]
        
        strikes = np.sort(current_skew.Strike.drop_duplicates().values)
        
        
        store_expiry_data = current_base_iv
        
        for strike in strikes:
            skew_strike = current_skew.loc[current_skew.Strike==strike,'skew']
            skew_strike = skew_strike[~skew_strike.index.duplicated(keep='last')]
            skew_strike.rename(strike,inplace=True)
        
            store_expiry_data = pd.concat([store_expiry_data,skew_strike],axis=1)
            
        store_expiry_data.fillna(method='ffill',inplace=True)
        store_expiry_data.fillna(method='bfill',inplace=True)
        
        output = store_expiry_data[strikes].apply(lambda x: x*store_expiry_data.baseiv )
        
        lyra_skews[expiry] = output
    
    
    lyra_skews_hourly = {}
    
    for expiry in expiries:
        hourly_skew = lyra_skews[expiry].resample('1h',label='right').last()
        hourly_skew.fillna(method='ffill',inplace=True)
        hourly_skew.fillna(method='bfill',inplace=True)
    
        lyra_skews_hourly[expiry] = hourly_skew
        
    return lyra_skews_hourly
