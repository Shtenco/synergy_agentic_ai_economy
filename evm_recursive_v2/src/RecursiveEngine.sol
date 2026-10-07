// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;
import "./TestToken.sol";
import "./CPMMPool.sol";
import "./Treasury.sol";
import "./CollateralVault.sol";

contract RecursiveEngine {
    TestToken public immutable x; TestToken public immutable z; TestToken public immutable u; TestToken public immutable c;
    Treasury public immutable treasury; CollateralVault public immutable vault;
    CPMMPool public immutable xu; CPMMPool public immutable zu; CPMMPool public immutable xz; CPMMPool public immutable xc; CPMMPool public immutable zc;
    address public owner; uint16 public reserveFloorBps=2000; uint256 public investorDividend=0.02 ether;
    modifier onlyOwner(){require(msg.sender==owner,"OWNER");_;}

    constructor(address X,address Z,address U,address C,address T,address V,address XU,address ZU,address XZ,address XC,address ZC){
        owner=msg.sender;x=TestToken(X);z=TestToken(Z);u=TestToken(U);c=TestToken(C);treasury=Treasury(T);vault=CollateralVault(V);
        xu=CPMMPool(XU);zu=CPMMPool(ZU);xz=CPMMPool(XZ);xc=CPMMPool(XC);zc=CPMMPool(ZC);
    }

    function mintSellX(uint256 a) external onlyOwner returns(uint256 out){x.mint(address(this),a);x.approve(address(xu),a);out=xu.swapExactIn(address(x),a,0,address(treasury));}
    function mintSellZ(uint256 a) external onlyOwner returns(uint256 out){z.mint(address(this),a);z.approve(address(zu),a);out=zu.swapExactIn(address(z),a,0,address(treasury));}
    function addXZ(uint256 ax,uint256 az) external onlyOwner returns(uint256 lp){x.mint(address(this),ax);z.mint(address(this),az);x.approve(address(xz),ax);z.approve(address(xz),az);lp=xz.addLiquidity(ax,az,address(this));}
    function pledgeLP(address p,uint256 a,uint8 tier) external onlyOwner{CPMMPool(p).approve(address(vault),a);vault.pledge(p,a,tier);}

    function drawAndAddHardLP(address p,address hard,uint256 hardAmount,uint8 softKind,uint8 tier) external onlyOwner returns(uint256 lp){
        uint256 beforeNav=hardNav();
        vault.draw(hard,hardAmount,address(this));
        require(freeHard()*10000>=beforeNav*reserveFloorBps,"RESERVE_FLOOR");
        TestToken soft=softKind==0?x:z;
        CPMMPool pool=CPMMPool(p);
        uint256 softAmount;
        if(pool.token0()==address(soft))softAmount=hardAmount*pool.reserve0()/pool.reserve1();
        else softAmount=hardAmount*pool.reserve1()/pool.reserve0();
        soft.mint(address(this),softAmount);
        uint256 a0=pool.token0()==hard?hardAmount:softAmount;
        uint256 a1=pool.token1()==hard?hardAmount:softAmount;
        TestToken(pool.token0()).approve(p,a0);TestToken(pool.token1()).approve(p,a1);
        lp=pool.addLiquidity(a0,a1,address(this));
        pool.approve(address(vault),lp);vault.pledge(p,lp,tier);
        require(hardNav()==beforeNav,"NO_FREE_HARDNAV");
    }

    function freeHard() public view returns(uint256){return u.balanceOf(address(treasury))+c.balanceOf(address(treasury));}
    function hardNav() public view returns(uint256){
        uint256 t=freeHard();
        t+=u.balanceOf(address(vault))+c.balanceOf(address(vault));
        t+=u.balanceOf(address(xu))+u.balanceOf(address(zu));
        t+=c.balanceOf(address(xc))+c.balanceOf(address(zc));
        t+=u.balanceOf(address(this))+c.balanceOf(address(this));
        return t;
    }
}
