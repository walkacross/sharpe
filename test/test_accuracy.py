#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sharpe.utils.mock_data import create_toy_feature
from sharpe.data.data_source import DataSource
from sharpe.environment import TradingEnv
from sharpe.core.context import Context
from sharpe.mod.sys_account.api import order_target_weights
from sharpe.const import POSITION_DIRECTION
import pdb
import unittest

class TestOneObjectImplmentCorrection(unittest.TestCase):
    
    def setUp(self):
        pass
    
    def test_first_step_buy_and_then_sell(self):
        feature_df, price_s = create_toy_feature(order_book_ids_number=1, feature_number=3, random_seed=111)
        data_source = DataSource(feature_df=feature_df, price_s=price_s)
        order_book_ids  = data_source.get_available_order_book_ids() 
            
        STOCK_INIT_CASH = 1000000
        FUTURE_INIT_CASH = 10000
        starting_cash = {"STOCK":STOCK_INIT_CASH, "FUTURE": FUTURE_INIT_CASH}
        commission_rate = 0.0005 #default value in environment
        tax_rate = 0.001         #default value in environment
            
        commission_multiplier=2
        min_commission=5
        tax_multiplier=1
        
        
        """
         
        MANUALly check
        
        first date: 
            target weight: 0.5
            price at end: 77.53
            
            target quantity: 6400
            deal_money = 6400 * 77.53 = 496192
            commition_fee_total = 496.192
            availabel_cash_stock = 1000000 - 496192 - 496.192 = 503311.808
            total_value_account_stock = 496192 + 503311.808 = 999503.808
            total_value_account = 999503.808 + 10000 = 1009503.808
            returns = 1009503.808/1010000  -1 = -0.0004912792079208028
        
        second date:
            target weight: 0.2
            price at end: 69.78
            
            stock_account_at_this_time: 6400*69.78 + 503311.808 =  949903.808
            target quantity: 2700
            to_trade_quantity: 3700
            deal_money = 3700 * 69.78 = 258186
            commition_fee_total = 258186 * (0.001 + 0.001) = 516.372
            
            available_cash_stock = 503311.808 + 258186 - 516.372 = 760981.436
            
            total_value_account_stock = 760981.436 + 2700*69.78 = 949387.436
            
            total_value_account = 949387.436 + 10000 =959387.436
            
            return = 959387.436/1009503.808 - 1 = -0.04964455963696568
        
        """
        
        env= TradingEnv(data_source=data_source, 
                        look_backward_window=2, 
                        mode="non-rl", 
                        starting_cash= starting_cash,
                        commission_multiplier=commission_multiplier,
                        min_commission=min_commission,
                        tax_multiplier=tax_multiplier)

        
        
        print('--------------------------------------------')
        #print("current context \n",Context.get_instance().__dict__)
        context = Context.get_instance()


        #stock account
        expect_market_value_stock = 0
        expect_cash_stock = starting_cash["STOCK"]
        expect_total_value_stock = expect_cash_stock + expect_market_value_stock
                
        #future account
        expect_market_value_future = 0
        expect_cash_future = starting_cash["FUTURE"]
        expect_total_value_future = expect_cash_future + expect_market_value_future
        expect_total_value_future = expect_total_value_future
        
        #portfolio
        expect_total_value_portfolio = expect_total_value_stock + expect_total_value_future
        
        
        trading_dts = context.get_available_trading_dts()
        first_trading_dt = trading_dts[0]
        order_book_id = order_book_ids[0]
            
        
        #
        target_weight = 0.5
        print("------------the first trading date: {}--------------------------".format(env.trading_dt))        
        to_submit_orders = order_target_weights({order_book_id:target_weight})
        
        submit_order = to_submit_orders[0]
        # ============================================================= #
        # step1: test trade correctness                                 #
        # ============================================================= #
        expect_deal_price1 = data_source.get_last_price(order_book_id = order_book_id , dt=first_trading_dt)
        print("fisrt date end price: {}".format(expect_deal_price1))
        expect_quantity1 = (STOCK_INIT_CASH * target_weight)/ expect_deal_price1
        expect_quantity1 = int(round(expect_quantity1/100) * 100)
        
        print((submit_order.quantity, expect_quantity1))
        
        expect_deal_money = expect_deal_price1 * expect_quantity1        
        expect_commission_fee = expect_deal_money * commission_rate * commission_multiplier
        expect_tax = 0 # no tax rate when buy
        expect_transaction_cost = expect_commission_fee + expect_tax

        
        
        state, reward, is_done, info = env.step(action=to_submit_orders)
            
        
        true_order = context.tracker._orders[0]
        print(true_order)
        first_trade = context.tracker._trades[0]
        
        #first_trade = first_trade
        self.assertEqual(first=first_trade["order_book_id"], second= order_book_id)
        self.assertEqual(first=first_trade["trading_datetime"], second = first_trading_dt.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual(first=first_trade["last_price"], second=expect_deal_price1)
        self.assertEqual(first=first_trade["commission"], second=expect_commission_fee)
        self.assertEqual(first=first_trade["tax"], second=expect_tax)
        self.assertEqual(first=first_trade["transaction_cost"], second=expect_transaction_cost)
            
        # =========================================== #
        # step2.1 test position                       #
        # step2.2 test account                        #
        # step2.3 test portfolio                      #
        # =========================================== #
        
        # portfolio and accounts change after trading
        #stock account
        expect_market_value_stock = expect_deal_money     #496192
        expect_cash_stock = starting_cash["STOCK"] - expect_market_value_stock - expect_transaction_cost #502448.2768
        expect_total_value_stock = expect_cash_stock + expect_market_value_stock
        
        portfolio = Context.get_instance().portfolio
        stock_account = portfolio.stock_account
        position1 = stock_account.get_position(order_book_id, POSITION_DIRECTION.LONG)
        print(expect_market_value_stock, position1.market_value)
        #pdb.set_trace()
        assert expect_market_value_stock == position1.market_value
        print(expect_market_value_stock, stock_account.market_value)     
        print(expect_cash_stock, stock_account.total_cash)
        print(expect_total_value_stock, stock_account.total_value)
        
        self.assertEqual(expect_market_value_stock, position1.market_value)
        self.assertEqual(expect_market_value_stock, stock_account.market_value)
        self.assertEqual(expect_cash_stock, stock_account.total_cash)
        self.assertEqual(expect_total_value_stock, stock_account.total_value)
                    
        
        # #future account
        expect_market_value_future = 0
        expect_cash_future = starting_cash["FUTURE"]
        expect_total_value_future = expect_cash_future + expect_market_value_future
            
        # #portfolio
        expect_cash_portfolio = expect_cash_stock + expect_cash_future
        expect_market_value = expect_market_value_stock + expect_market_value_future
        expect_total_value_portfolio_new = expect_total_value_stock + expect_total_value_future
        print(expect_cash_portfolio, portfolio.cash)
        print(expect_market_value, portfolio.market_value)
        print(expect_total_value_portfolio_new, portfolio.total_value)   
        portfolio_record = Context.get_instance().tracker._total_portfolio[0]
        #print(portfolio_record)
        expect_reward = (expect_total_value_portfolio_new / expect_total_value_portfolio) -1
        print(expect_reward, reward, portfolio.daily_returns)
        #pdb.set_trace()
        self.assertEqual(expect_cash_portfolio, portfolio.cash)
        self.assertEqual(expect_market_value, portfolio.market_value)
        self.assertEqual(expect_total_value_portfolio_new, portfolio.total_value)
        self.assertEqual(expect_reward, reward)
        
        
        # ============================================================== #
        # the next dt trade                                              #
        # ============================================================== #
        print("------------the second trading date: {}--------------------------".format(env.trading_dt))
        target_weight = 0.2
       
        second_trading_dt = trading_dts[1]
        print(second_trading_dt, env.trading_dt)
        self.assertEqual(second_trading_dt, env.trading_dt)
        
        
        to_submit_orders = order_target_weights({order_book_id: target_weight})
        order = to_submit_orders[0]
        #pdb.set_trace()
        
        expect_deal_price = data_source.get_last_price(order_book_id = order_book_id , dt=second_trading_dt)
        print("second date end price: {}".format(expect_deal_price))
        #here is the point: we need to get the updated account total value
        expect_deal_price = data_source.get_last_price(order_book_id = order_book_id , dt=second_trading_dt) #69.78
        
        expect_market_value_stock = expect_quantity1 * expect_deal_price
        expect_cash_stock =  expect_cash_stock
        expect_total_value_stock = expect_cash_stock + expect_market_value_stock
 
        expect_quantity2 = (expect_total_value_stock * target_weight)/ expect_deal_price
        expect_quantity2 = int(round(expect_quantity2/100) * 100)
        
        to_trade_quantity = abs(expect_quantity2 - expect_quantity1)
        #expect_quantity = true_order.quantity  #allow not 100 times
        #print((, expetrue_orderct_quantity))
        expect_deal_money = expect_deal_price * to_trade_quantity
 
        expect_commission_fee = expect_deal_money * commission_rate * commission_multiplier 
        expect_tax = expect_deal_money * tax_rate * tax_multiplier # no tax rate when buy, but charge when sell
        expect_transaction_cost = expect_commission_fee + expect_tax
        #pdb.set_trace()

        
        state, reward, is_done, info = env.step(action=to_submit_orders)
            
        true_order = context.tracker._orders[1]
        # if sell, allow the quantity is not 100 times
        print(true_order)        
        second_trade = context.tracker._trades[1]
        print(second_trade["order_book_id"], order_book_id)
        print(second_trade["trading_datetime"], second_trading_dt.strftime("%Y-%m-%d %H:%M:%S"))
        print(second_trade["last_price"], expect_deal_price)
        print(second_trade["commission"], expect_commission_fee)
        print(second_trade["tax"], expect_tax)
        print(second_trade["transaction_cost"], expect_transaction_cost)
        self.assertEqual(first=second_trade["order_book_id"], second= order_book_id)
        self.assertEqual(first=second_trade["trading_datetime"], second = second_trading_dt.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual(first=second_trade["last_price"], second=expect_deal_price)
        self.assertEqual(first=second_trade["commission"], second=expect_commission_fee)
        self.assertEqual(first=second_trade["tax"], second=expect_tax)
        self.assertEqual(first=second_trade["transaction_cost"], second=expect_transaction_cost)
        #pdb.set_trace()


        # here is important and think why use settlement price rather the trade price
        # the special case. when sell at the end time of the trading time. the settlement price is equal to the trade price
        expect_cash_stock_settlement = expect_cash_stock + expect_deal_money -  expect_transaction_cost
        expect_settlement_price = data_source.get_last_price(order_book_id = order_book_id , dt=second_trading_dt)

        position1 = stock_account.get_position(order_book_id, POSITION_DIRECTION.LONG)
        print(position1)
        #expect_remaining_market_value_stock_settlement = (first_trade["last_quantity"] - second_trade["last_quantity"]) * expect_settlement_price
        expect_market_value_stock_settlement =  position1.quantity * expect_settlement_price
        expect_total_value_stock_settlement = expect_cash_stock_settlement + expect_market_value_stock_settlement
        
        
        portfolio = Context.get_instance().portfolio
        stock_account = portfolio.stock_account
        position1 = stock_account.get_position(order_book_id, POSITION_DIRECTION.LONG)
        #expect_reward = (expect_total_value_settlement - self.expect_total_value_settlement) / self.expect_total_value_settlement
            
        print(expect_market_value_stock_settlement, position1.market_value)
        print(expect_market_value_stock_settlement, stock_account.market_value)     
        print(expect_cash_stock_settlement, stock_account.total_cash)
        print(expect_total_value_stock_settlement, stock_account.total_value)
        #pdb.set_trace()
        self.assertEqual(expect_market_value_stock_settlement, position1.market_value)
        self.assertEqual(expect_market_value_stock_settlement, stock_account.market_value)
        self.assertEqual(expect_cash_stock_settlement, stock_account.total_cash)
        self.assertEqual(expect_total_value_stock_settlement, stock_account.total_value)
        



        expect_cash_future_settlement = starting_cash["FUTURE"]
        expect_market_value_future_settlement = 0
        expect_total_value_future_settlement = expect_cash_future_settlement + expect_market_value_future_settlement
        
        expect_cash_portfolio_settlement = expect_cash_stock_settlement + expect_cash_future_settlement
        expect_market_value_portfolio_settlement = expect_market_value_stock_settlement + expect_market_value_future_settlement
        expect_total_value_settlement_portfolio_2 = expect_total_value_stock_settlement + expect_total_value_future_settlement

        #pdb.set_trace()
        print(expect_cash_portfolio_settlement,  portfolio.cash)
        print(expect_market_value_portfolio_settlement, portfolio.market_value)
        print(expect_total_value_settlement_portfolio_2, portfolio.total_value)   
        expect_reward = (expect_total_value_settlement_portfolio_2 / expect_total_value_portfolio_new) -1
        print(expect_reward, reward, portfolio.daily_returns)
        #pdb.set_trace()
        self.assertEqual(expect_cash_portfolio_settlement, portfolio.cash)
        self.assertEqual(expect_market_value_portfolio_settlement, portfolio.market_value)
        self.assertEqual(expect_total_value_settlement_portfolio_2, portfolio.total_value)
        self.assertEqual(expect_reward, reward)

        print("------------the third trading date: {}--------------------------".format(env.trading_dt))
        third_trading_dt = trading_dts[2]
        print(second_trading_dt, env.trading_dt)
        
        target_weight =  0.0
        to_submit_orders = order_target_weights({order_book_id:target_weight})
        
        
        expect_deal_price = data_source.get_last_price(order_book_id = order_book_id , dt=third_trading_dt)
        print("third date end price: {}".format(expect_deal_price)) #72.5
        expect_quantity = 0  #allow not 100 times
        to_trade_quantity = expect_quantity2
        # #print((, expetrue_orderct_quantity))
        expect_deal_money = expect_deal_price * to_trade_quantity
 
        expect_commission_fee = expect_deal_money * commission_rate * commission_multiplier
        expect_tax = expect_deal_money * tax_rate * tax_multiplier # no tax rate when buy
        expect_transaction_cost = expect_commission_fee + expect_tax
        
        
        
        
        
        state, reward, is_done, info = env.step(action=to_submit_orders)
        
        order = to_submit_orders[0]
        true_order = context.tracker._orders[2]
        # if sell, allow the quantity is not 100 times
        print(true_order)

        third_trade = context.tracker._trades[2]
        print(third_trade["order_book_id"], order_book_id)
        print(third_trade["trading_datetime"], second_trading_dt.strftime("%Y-%m-%d %H:%M:%S"))
        print(third_trade["last_price"], expect_deal_price)
        print(third_trade["commission"], expect_commission_fee)
        print(third_trade["tax"], expect_tax)
        print(third_trade["transaction_cost"], expect_transaction_cost)
        #pdb.set_trace()
        self.assertEqual(first=third_trade["order_book_id"], second= order_book_id)
        self.assertEqual(first=third_trade["trading_datetime"], second = third_trading_dt.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual(first=third_trade["last_price"], second=expect_deal_price)
        self.assertEqual(first=third_trade["commission"], second=expect_commission_fee)
        self.assertEqual(first=third_trade["tax"], second=expect_tax)
        self.assertEqual(first=third_trade["transaction_cost"], second=expect_transaction_cost)



        # # here is important and think why use settlement price rather the trade price
        # # the special case. when sell at the end time of the trading time. the settlement price is equal to the trade price
        expect_cash_stock_settlement = expect_cash_stock_settlement + expect_deal_money -  expect_transaction_cost
        expect_settlement_price = data_source.get_last_price(order_book_id = order_book_id , dt=third_trading_dt)
        
        position = stock_account.get_position(order_book_id, POSITION_DIRECTION.LONG)
        print(position)
        expect_market_value_stock_settlement =  position.quantity * expect_settlement_price
        print("expect_market_value_stock_settlement: {}".format(expect_market_value_stock_settlement))
        #expect_remaining_market_value_stock_settlement = (first_trade["last_quantity"] - second_trade["last_quantity"]) * expect_settlement_price
        expect_total_value_stock_settlement = expect_cash_stock_settlement + expect_market_value_stock_settlement
            
        
        portfolio = Context.get_instance().portfolio
        stock_account = portfolio.stock_account
        position1 = stock_account.get_position(order_book_id, POSITION_DIRECTION.LONG)
            
        print(expect_market_value_stock_settlement, position1.market_value)
        print(expect_market_value_stock_settlement, stock_account.market_value)     
        print("---------------------")
        print(expect_cash_stock_settlement, stock_account.total_cash)
        print(expect_total_value_stock_settlement, stock_account.total_value)
        #pdb.set_trace()
        self.assertEqual(expect_market_value_stock_settlement, position1.market_value)
        self.assertEqual(expect_market_value_stock_settlement, stock_account.market_value)
        self.assertEqual(expect_cash_stock_settlement, stock_account.total_cash)
        self.assertEqual(expect_total_value_stock_settlement, stock_account.total_value)



        expect_cash_future_settlement = starting_cash["FUTURE"]
        expect_market_value_future_settlement = 0
        expect_total_value_future_settlement = expect_cash_future_settlement + expect_market_value_future_settlement

        expect_cash_portfolio_settlement = expect_cash_stock_settlement + expect_cash_future_settlement
        expect_market_value_portfolio_settlement = expect_market_value_stock_settlement + expect_market_value_future_settlement
        expect_total_value_settlement_portfolio = expect_total_value_stock_settlement + expect_total_value_future_settlement


        print(expect_cash_portfolio_settlement,  portfolio.cash)
        print(expect_market_value_portfolio_settlement, portfolio.market_value)
        print(expect_total_value_settlement_portfolio, portfolio.total_value)   
        expect_reward = (expect_total_value_settlement_portfolio / expect_total_value_settlement_portfolio_2) -1
        print(expect_reward, reward, portfolio.daily_returns)
        print(portfolio.cash, portfolio.market_value, portfolio.total_value)
        #pdb.set_trace()
        self.assertEqual(expect_cash_portfolio_settlement, portfolio.cash)
        self.assertEqual(expect_market_value_portfolio_settlement, portfolio.market_value)
        self.assertEqual(expect_total_value_settlement_portfolio, portfolio.total_value)
        self.assertEqual(expect_reward, reward)
        
        
        

if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTest(TestOneObjectImplmentCorrection("test_first_step_buy_and_then_sell"))
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

                