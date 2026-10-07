// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;

interface IVaultERC20 {
    function transferFrom(address,address,uint256) external returns (bool);
}
interface IVaultPool {
    function token0() external view returns (address);
    function token1() external view returns (address);
    function reserve0() external view returns (uint256);
    function reserve1() external view returns (uint256);
    function totalSupply() external view returns (uint256);
}
interface IVaultOracle { function price(address) external view returns (uint256); }
interface IVaultTreasury { function move(address,address,uint256) external; }

contract CollateralVault {
    address public owner;
    address public operator;
    IVaultOracle public oracle;
    IVaultTreasury public treasury;
    uint16 public maxReuseBps=5000;
    uint16 public secondaryTierBps=2500;
    uint16 public minHealthBps=12500;

    struct Config {uint16 factorBps; bool enabled;}
    mapping(address=>Config) public poolConfig;
    mapping(address=>bool) public hardToken;
    mapping(address=>mapping(uint8=>uint256)) public pledgedLP;
    address[] public pools;
    uint256 public debtUsdWad;

    modifier onlyOwner(){require(msg.sender==owner,"OWNER");_;}
    modifier onlyOperator(){require(msg.sender==operator,"OP");_;}

    constructor(address o,address t){owner=msg.sender;operator=msg.sender;oracle=IVaultOracle(o);treasury=IVaultTreasury(t);}
    function setOperator(address a) external onlyOwner {operator=a;}
    function setHardToken(address t,bool on) external onlyOwner {hardToken[t]=on;}
    function setRisk(uint16 reuseBps,uint16 tier1Bps,uint16 healthBps) external onlyOwner {
        require(reuseBps<=7000 && tier1Bps<=5000 && healthBps>=11000,"RISK");
        maxReuseBps=reuseBps; secondaryTierBps=tier1Bps; minHealthBps=healthBps;
    }
    function configurePool(address p,uint16 factorBps) external onlyOwner {
        require(factorBps<=8000,"FACTOR");
        if(!poolConfig[p].enabled)pools.push(p);
        poolConfig[p]=Config(factorBps,true);
    }
    function pledge(address p,uint256 a,uint8 tier) external onlyOperator {
        require(poolConfig[p].enabled && tier<=1,"POOL");
        require(IVaultERC20(p).transferFrom(msg.sender,address(this),a),"PLEDGE");
        pledgedLP[p][tier]+=a;
    }

    function eligibleCollateralUsdWad() public view returns(uint256 total){
        for(uint256 i=0;i<pools.length;i++){
            address p=pools[i]; Config memory cfg=poolConfig[p];
            uint256 ts=IVaultPool(p).totalSupply(); if(ts==0)continue;
            uint256 hardUsd=_poolHardUsd(p);
            uint256 t0=hardUsd*pledgedLP[p][0]/ts;
            uint256 t1=hardUsd*pledgedLP[p][1]/ts;
            uint256 discounted=t0+t1*secondaryTierBps/10000;
            total+=discounted*cfg.factorBps/10000;
        }
    }
    function creditLimitUsdWad() public view returns(uint256){return eligibleCollateralUsdWad()*maxReuseBps/10000;}
    function healthBps() public view returns(uint256){
        if(debtUsdWad==0)return type(uint256).max;
        return eligibleCollateralUsdWad()*10000/debtUsdWad;
    }
    function draw(address hard,uint256 amount,address to) external onlyOperator {
        require(hardToken[hard],"NOT_HARD");
        uint256 usd=amount*oracle.price(hard)/1e18;
        require(debtUsdWad+usd<=creditLimitUsdWad(),"LIMIT");
        debtUsdWad+=usd;
        require(healthBps()>=minHealthBps,"HF");
        treasury.move(hard,to,amount);
    }

    function _poolHardUsd(address p) internal view returns(uint256 total){
        IVaultPool pool=IVaultPool(p);
        address a=pool.token0(); address b=pool.token1();
        if(hardToken[a])total+=pool.reserve0()*oracle.price(a)/1e18;
        if(hardToken[b])total+=pool.reserve1()*oracle.price(b)/1e18;
    }
}
