// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;

interface IERC20Like {
    function balanceOf(address) external view returns (uint256);
    function transfer(address,uint256) external returns (bool);
    function transferFrom(address,address,uint256) external returns (bool);
}

contract CPMMPool {
    address public immutable token0;
    address public immutable token1;
    uint24 public immutable feeBps;
    uint256 public reserve0;
    uint256 public reserve1;
    string public name;
    string public symbol;
    uint8 public constant decimals = 18;
    uint256 public totalSupply;
    mapping(address=>uint256) public balanceOf;
    mapping(address=>mapping(address=>uint256)) public allowance;

    constructor(address a,address b,uint24 f,string memory n,string memory s){
        require(a!=b && a!=address(0) && b!=address(0),"TOKENS");
        require(f<10000,"FEE");
        token0=a; token1=b; feeBps=f; name=n; symbol=s;
    }

    function approve(address s,uint256 v) external returns(bool){allowance[msg.sender][s]=v;return true;}
    function transfer(address to,uint256 v) external returns(bool){_transfer(msg.sender,to,v);return true;}
    function transferFrom(address f,address to,uint256 v) external returns(bool){
        uint256 a=allowance[f][msg.sender]; require(a>=v,"ALLOW");
        if(a!=type(uint256).max) allowance[f][msg.sender]=a-v;
        _transfer(f,to,v); return true;
    }

    function addLiquidity(uint256 a0,uint256 a1,address to) external returns(uint256 shares){
        require(a0>0 && a1>0,"AMOUNT");
        _pull(token0,msg.sender,a0); _pull(token1,msg.sender,a1);
        if(totalSupply==0) shares=_sqrt(a0*a1);
        else {
            uint256 s0=a0*totalSupply/reserve0;
            uint256 s1=a1*totalSupply/reserve1;
            shares=s0<s1?s0:s1;
        }
        require(shares>0,"SHARES");
        totalSupply+=shares; balanceOf[to]+=shares; _sync();
    }

    function quoteOut(address inToken,uint256 amountIn) public view returns(uint256 out){
        require(amountIn>0,"AMOUNT");
        bool z=inToken==token0; require(z || inToken==token1,"TOKEN");
        uint256 rIn=z?reserve0:reserve1;
        uint256 rOut=z?reserve1:reserve0;
        require(rIn>0 && rOut>0,"LIQ");
        uint256 inWithFee=amountIn*(10000-feeBps);
        out=(rOut*inWithFee)/(rIn*10000+inWithFee);
    }

    function swapExactIn(address inToken,uint256 amountIn,uint256 minOut,address to) external returns(uint256 out){
        bool z=inToken==token0; require(z || inToken==token1,"TOKEN");
        address outToken=z?token1:token0;
        out=quoteOut(inToken,amountIn); require(out>=minOut,"MIN_OUT");
        _pull(inToken,msg.sender,amountIn);
        require(IERC20Like(outToken).transfer(to,out),"OUT");
        _sync();
    }

    function spotPrice1Per0Wad() external view returns(uint256){
        require(reserve0>0,"LIQ"); return reserve1*1e18/reserve0;
    }

    function _sync() internal {
        reserve0=IERC20Like(token0).balanceOf(address(this));
        reserve1=IERC20Like(token1).balanceOf(address(this));
    }
    function _pull(address t,address f,uint256 a) internal {require(IERC20Like(t).transferFrom(f,address(this),a),"PULL");}
    function _transfer(address f,address t,uint256 v) internal {require(t!=address(0) && balanceOf[f]>=v,"LP");balanceOf[f]-=v;balanceOf[t]+=v;}
    function _sqrt(uint256 y) internal pure returns(uint256 z){
        if(y==0)return 0; z=y; uint256 x=y/2+1;
        while(x<z){z=x;x=(y/x+x)/2;}
    }
}
