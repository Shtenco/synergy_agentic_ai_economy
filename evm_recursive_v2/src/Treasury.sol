// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;
interface ITreasuryERC20{function transfer(address,uint256) external returns(bool);function transferFrom(address,address,uint256) external returns(bool);}
contract Treasury{
    address public owner;
    mapping(address=>bool) public operator;
    mapping(address=>uint256) public distributableRevenue;
    modifier onlyOwner(){require(msg.sender==owner,"OWNER");_;}
    modifier onlyOperator(){require(operator[msg.sender],"OP");_;}
    constructor(){owner=msg.sender;operator[msg.sender]=true;}
    function setOperator(address a,bool on) external onlyOwner{operator[a]=on;}
    function depositExternalRevenue(address t,uint256 a) external{require(ITreasuryERC20(t).transferFrom(msg.sender,address(this),a),"PULL");distributableRevenue[t]+=a;}
    function move(address t,address to,uint256 a) external onlyOperator{require(ITreasuryERC20(t).transfer(to,a),"MOVE");}
    function payDividend(address t,address to,uint256 a) external onlyOperator{require(distributableRevenue[t]>=a,"NO_REVENUE");distributableRevenue[t]-=a;require(ITreasuryERC20(t).transfer(to,a),"PAY");}
}
