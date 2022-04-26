import numpy as np
import pandas as pd
from scipy.stats import norm 


def blackScholesPrice(S,K,T,sigma,r,flag):
    
    d1 = ( np.log(S/K)+(r+sigma**2/2) * T ) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)

    price = flag*S*norm.cdf(flag*d1)-flag*K*np.exp(-r*T)*norm.cdf(flag*d2)
    
    return price


def runOptionBacktest(weeklyInputs,weeklyVol,freq,interest,currency,r,strike_otm,strategy,strike_rounding=False):
    # weeklyInputData Pandas dataframe, weekly frequency
    # Columns required, open,close,position
    
    outputData = pd.DataFrame(index=weeklyInputs.index)
    outputData['optionReturns'] = 0
    
    T = freq/365
    
    spotPrices = weeklyInputs.open
    
    if strike_rounding:
        callStrikes = round(spotPrices * (1+strike_otm)/100.0,0)*100.0
        putStrikes = round(spotPrices * (1-strike_otm)/100.0,0)*100.0
    else:
        callStrikes = spotPrices * (1+strike_otm)
        putStrikes = spotPrices * (1-strike_otm)
    
    outputData['sigma_open'] = weeklyVol.close.shift(fill_value=weeklyVol.close.iloc[0])/100
    outputData['sigma_close'] = weeklyVol.close/100
    
    
    outputData['callPrices'] = blackScholesPrice(spotPrices,callStrikes,T,outputData['sigma_open'],r,1)/spotPrices
    outputData['putPrices'] = blackScholesPrice(spotPrices,putStrikes,T,outputData['sigma_open'],r,-1)/spotPrices
    
    outputData['callPayoff'] = np.where(weeklyInputs.close > callStrikes,weeklyInputs.close - callStrikes,0)
    outputData['putPayoff'] = np.where(putStrikes > weeklyInputs.close,putStrikes - weeklyInputs.close,0)
        
    if strategy == 'optionBuyer':
        maskLong = (weeklyInputs.position > 0)
        maskShort = (weeklyInputs.position < 0)
        
        if currency == 'USD':
            outputData.loc[maskLong,'optionReturns'] = interest / (outputData.loc[maskLong,'callPrices']*weeklyInputs.loc[maskLong,'open']) * outputData.loc[maskLong,'callPayoff'] -interest
            outputData.loc[maskShort,'optionReturns'] = interest / (outputData.loc[maskShort,'putPrices']*weeklyInputs.loc[maskShort,'open']) * outputData.loc[maskShort,'putPayoff'] -interest
        elif currency == 'ETH':
            outputData.loc[maskLong,'optionReturns'] = interest / outputData.loc[maskLong,'callPrices'] * outputData.loc[maskLong,'callPayoff']/weeklyInputs.loc[maskLong,'close'] -interest
            outputData.loc[maskShort,'optionReturns'] = interest / outputData.loc[maskShort,'putPrices'] * outputData.loc[maskShort,'putPayoff']/weeklyInputs.loc[maskShort,'close'] -interest
     
    elif strategy == 'straddleBuyer':
        if currency == 'USD':
            outputData['optionReturns'] = (interest/2) / (outputData['callPrices']*weeklyInputs['open']) * outputData['callPayoff'] + (interest/2) / (outputData['putPrices']*weeklyInputs['open']) * outputData['putPayoff']-interest
        elif currency == 'ETH':
            callsBought = (interest/2) / outputData['callPrices']
            putsBought = (interest/2) / outputData['putPrices']
            
            callPayoff = callsBought*outputData['callPayoff']/weeklyInputs['close']
            putPayoff =  putsBought*outputData['putPayoff']/weeklyInputs['close']
            outputData['optionReturns'] = callPayoff + putPayoff - interest
            
    elif strategy == 'optionSeller':
        maskLong = (weeklyInputs.position > 0)
        maskShort = (weeklyInputs.position < 0)
        
        if currency == 'USD':
            outputData.loc[maskShort,'optionReturns'] = -interest / (weeklyInputs.loc[maskShort,'open']) * outputData.loc[maskShort,'callPayoff'] + interest*outputData.loc[maskShort,'callPrices']
            outputData.loc[maskLong,'optionReturns'] = -interest / (weeklyInputs.loc[maskLong,'open']) * outputData.loc[maskLong,'putPayoff'] + interest*outputData.loc[maskLong,'putPrices']
        elif currency == 'ETH':
            outputData.loc[maskShort,'optionReturns'] = -interest * outputData.loc[maskShort,'callPayoff']/weeklyInputs.loc[maskShort,'close'] + interest*outputData.loc[maskShort,'callPrices']
            outputData.loc[maskLong,'optionReturns'] = -interest * outputData.loc[maskLong,'putPayoff']/weeklyInputs.loc[maskLong,'close'] + interest*outputData.loc[maskLong,'putPrices']

    elif strategy == 'straddleSeller':
        if currency == 'USD':
            callsSold = (interest/2) / weeklyInputs['open']
            putsSold = (interest/2) / weeklyInputs['open'] #assuming atm puts
            callPremiumEarned = callsSold * (outputData['callPrices']*weeklyInputs['open'])
            putPremiumEarned = putsSold * (outputData['putPrices']*weeklyInputs['open'])
            callPayoff = - callsSold*outputData['callPayoff']
            putPayoff = - putsSold*outputData['putPayoff']
            outputData['optionReturns'] = callPremiumEarned + putPremiumEarned + callPayoff + putPayoff
        elif currency == 'ETH':
            callsSold = (interest/2)
            putsSold = (interest/2) #assuming atm puts
            callPremiumEarned = callsSold * outputData['callPrices']
            putPremiumEarned = putsSold * outputData['putPrices']
            callPayoff = - callsSold*outputData['callPayoff']/weeklyInputs['close']
            putPayoff = - putsSold*outputData['putPayoff']/weeklyInputs['close']
            outputData['optionReturns'] = callPremiumEarned + putPremiumEarned + callPayoff + putPayoff
    else:
        print(strategy+" is not a known option strategy")
    
    
    
    
    alpha = outputData.optionReturns.sum() / (outputData.shape[0]/52)
    
    return outputData,alpha




def runSqueethBacktest(weeklyInputs,weeklyVol,hourlyVol,freq,interest,currency,f,n0):

    outputData = pd.DataFrame(index=weeklyInputs.index)
    outputData['squeethReturns'] = 0

    #generate squeeth normalisation factors (i.e. funding)
    hourlyVol['mean_IV'] = (hourlyVol['open']+hourlyVol['close'])/2 /100
    hourlyVol['premium'] = (hourlyVol['mean_IV'])**2*f  # mark = index*sigma^2 * f 
    hourlyVol['hourlyChange'] = (1-hourlyVol['premium']/(17.5*24))
    hourlyVol['norm_factor'] = hourlyVol['hourlyChange'].cumprod()*n0
    # hourlyDVOL['norm_factor'] = 0.9
    
    weeklyNormFactor = hourlyVol.norm_factor.resample('7d',offset = '8h',label='left').first()
    
    weeklyNormFactor.drop(index=weeklyNormFactor.index[0], 
            axis=0, 
            inplace=True)
    
    
    outputData['norm_factor_open'] = weeklyNormFactor.shift(fill_value = weeklyNormFactor.iloc[0])
    outputData['norm_factor_close'] = weeklyNormFactor
    
    outputData['sigma_open'] = weeklyVol.close.shift(fill_value=weeklyVol.close.iloc[0])/100
    outputData['sigma_close'] = weeklyVol.close/100
    
    
    
    
    
    # #use norm factor, eth squared price and current IV to calculate live oSQTH price
    outputData['oSQTH_open'] = weeklyInputs['open']**2 * np.exp(outputData['sigma_open']**2 * f)*outputData['norm_factor_open']/10000
    outputData['oSQTH_close'] = weeklyInputs['close']**2 * np.exp(outputData['sigma_close']**2 * f)*outputData['norm_factor_close']/10000
    outputData['oSQTH_return'] = outputData['oSQTH_close'] / outputData['oSQTH_open'] -1
    outputData['oSQTH_fundingAPY'] = (outputData['norm_factor_close'] / outputData['norm_factor_open']-1)/(freq/365)
    
    
    
    maskLong = (weeklyInputs.position > 0)
    maskShort = (weeklyInputs.position < 0)
    
    if currency == 'USD':
        outputData.loc[maskLong,'squeethReturns'] = interest * weeklyInputs.loc[maskLong,'position'] * outputData.loc[maskLong,'oSQTH_return']
        outputData.loc[maskShort,'squeethReturns'] = interest/2 * weeklyInputs.loc[maskShort,'position'] * outputData.loc[maskShort,'oSQTH_return']#200% collateralise, add sqth liq logic

    elif currency == 'ETH':
        outputData['oSQTH_return_ETH'] = (outputData['oSQTH_close'] / weeklyInputs['close']) / (outputData['oSQTH_open'] / weeklyInputs['open']) -1
        outputData.loc[maskLong,'squeethReturns'] = interest * weeklyInputs.loc[maskLong,'position'] * outputData.loc[maskLong,'oSQTH_return_ETH']
        outputData.loc[maskShort,'squeethReturns'] = interest/2 * weeklyInputs.loc[maskShort,'position'] * outputData.loc[maskShort,'oSQTH_return_ETH'] #200% collateralise, add sqth liq logic
        
    alpha = outputData.squeethReturns.sum() / (outputData.shape[0]/52)
    
    return outputData,alpha

